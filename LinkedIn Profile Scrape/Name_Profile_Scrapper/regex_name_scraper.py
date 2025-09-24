import requests
import json
import time
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

class BrightDataLinkedInNameScraper:
    def __init__(self, api_token: str, dataset_id: str = "gd_l1viktl72bvl7bjuj0"):
        """
        Initialize LinkedIn name-based scraper with Bright Data API

        Args:
            api_token: Your Bright Data API token
            dataset_id: Your LinkedIn scraper dataset ID
        """
        self.api_token = api_token
        self.dataset_id = dataset_id
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        # 🔧 FIXED: Removed trailing space in base_url
        self.base_url = "https://api.brightdata.com/datasets/v3"

    def trigger_name_discovery(self, people: List[Dict[str, str]],
                             additional_params: Optional[Dict] = None) -> Dict:
        """
        Trigger LinkedIn profile discovery using names

        Args:
            people: List of dictionaries with 'first_name' and 'last_name'
            additional_params: Optional additional search parameters (company, location, etc.)

        Returns:
            API response with job details including snapshot_id
        """
        # Validate input data
        if not people:
            return {"error": "Empty people list provided"}

        for person in people:
            if 'first_name' not in person or 'last_name' not in person:
                return {"error": "Each person must have 'first_name' and 'last_name'"}

        api_url = f"{self.base_url}/trigger"
        params = {
            "dataset_id": self.dataset_id,
            "include_errors": "true",
            "type": "discover_new",
            "discover_by": "name"
        }

        # Add any additional search parameters
        if additional_params:
            params.update(additional_params)

        print(f"🔍 Triggering LinkedIn name discovery for {len(people)} people...")
        for i, person in enumerate(people, 1):
            name_display = f"{person['first_name']} {person['last_name']}"
            # Add company/location if provided in person data
            if 'company' in person:
                name_display += f" (Company: {person['company']})"
            if 'location' in person:
                name_display += f" (Location: {person['location']})"
            print(f"   {i}. {name_display}")

        print(f"API URL: {api_url}")
        print(f"Dataset ID: {self.dataset_id}")
        print(f"Search parameters: {params}")

        try:
            response = requests.post(api_url, headers=self.headers, json=people, params=params)

            print(f"Response status: {response.status_code}")

            if response.status_code in [200, 201, 202]:
                result = response.json()
                print(f"✅ Name discovery job triggered successfully!")
                print(f"Snapshot ID: {result.get('snapshot_id')}")
                return result
            else:
                print(f"❌ Request failed: {response.status_code}")
                print(f"Response: {response.text}")
                return {"error": f"HTTP {response.status_code}", "details": response.text}

        except Exception as e:
            print(f"❌ Error triggering discovery: {e}")
            return {"error": str(e)}

    def check_partial_results(self, snapshot_id: str) -> Tuple[Optional[List[Dict]], bool]:
        """
        Check for partial results from an ongoing job

        Returns:
            Tuple of (partial_data, job_complete)
        """
        url = f"{self.base_url}/snapshot/{snapshot_id}"
        params = {"format": "json"}

        try:
            response = requests.get(url, headers=self.headers, params=params)

            if response.status_code == 200:
                data = response.json()

                # Handle different response formats
                if isinstance(data, list):
                    return data, True
                elif isinstance(data, dict):
                    if 'data' in data:
                        return data['data'], True
                    elif 'results' in data:
                        return data['results'], True
                    # Check if there are partial results available
                    elif 'partial_data' in data:
                        return data['partial_data'], False
                    else:
                        return [data], True

                return [], True

            elif response.status_code == 202:
                # Job still running, check if any partial data is available
                try:
                    response_data = response.json()
                    if 'partial_results' in response_data:
                        return response_data['partial_results'], False
                    elif 'current_results' in response_data:
                        return response_data['current_results'], False
                except:
                    pass
                return None, False

            else:
                return None, False

        except Exception as e:
            print(f"⚠️ Error checking partial results: {e}")
            return None, False

    def calculate_quality_score(self, profile: Dict) -> int:
        """
        Enhanced quality scoring system for profile completeness (1-10 scale)

        Focuses on actual profile data completeness rather than just connections
        """
        score = 0
        max_score = 10

        # 1. Complete name (1 point)
        name = profile.get('name', '').strip()
        if name and len(name) > 5 and ' ' in name:  # Has both first and last name
            score += 1

        # 2. Current company information (2 points)
        current_company = profile.get('current_company', {})
        current_company_name = ''

        if isinstance(current_company, dict):
            current_company_name = current_company.get('name', '').strip()
        else:
            current_company_name = str(current_company).strip() if current_company else ''

        if not current_company_name:
            current_company_name = profile.get('current_company_name', '').strip()

        if current_company_name and current_company_name.lower() not in ['n/a', 'unknown', '-', '']:
            score += 2

        # 3. Job position/title (2 points)
        position = ''
        if isinstance(current_company, dict):
            position = current_company.get('title', '').strip()

        if not position:
            position = profile.get('position', '').strip()
        if not position:
            position = profile.get('current_position', '').strip()
        if not position:
            position = profile.get('headline', '').strip()

        if position and position.lower() not in ['n/a', 'unknown', '-', '']:
            score += 2

        # 4. About section (2 points if substantial)
        about = profile.get('about', '').strip()
        if about and len(about) > 50:  # Substantial about section
            score += 2
        elif about and len(about) > 10:  # Minimal about section
            score += 1

        # 5. Experience history (1 point)
        experience = profile.get('experience', [])
        if isinstance(experience, list) and len(experience) > 0:
            # Check if experience has actual data
            has_real_experience = any(
                exp.get('company', '').strip() and exp.get('title', '').strip()
                for exp in experience if isinstance(exp, dict)
            )
            if has_real_experience:
                score += 1

        # 6. Education information (1 point)
        education = profile.get('education', [])
        if isinstance(education, list) and len(education) > 0:
            # Check if education has actual data
            has_real_education = any(
                edu.get('school', '').strip() or edu.get('degree', '').strip()
                for edu in education if isinstance(edu, dict)
            )
            if has_real_education:
                score += 1

        # 7. Follower/connection count (1 point - indicates active profile)
        followers = profile.get('followers', 0)
        connections = profile.get('connections', 0)

        # Handle different formats for connections/followers
        try:
            if isinstance(followers, str):
                followers = int(followers.replace(',', '').replace('+', ''))
            if isinstance(connections, str):
                connections = int(connections.replace(',', '').replace('+', ''))

            if followers > 50 or connections > 50:  # Has some network presence
                score += 1
        except (ValueError, AttributeError):
            pass

        # Bonus: Profile URL exists and looks complete
        url = profile.get('url', '')
        if url and 'linkedin.com/in/' in url and len(url) > 30:
            # This is counted within the max score, not as bonus
            pass

        return min(score, max_score)  # Cap at maximum score

    def filter_quality_profiles(self, profiles: List[Dict], min_quality_score: int = 3) -> Tuple[List[Dict], List[Dict]]:
        """
        Filter profiles based on quality score and return both high and low quality lists

        Args:
            profiles: List of discovered profiles
            min_quality_score: Minimum score to be considered high-quality (1-10 scale)

        Returns:
            Tuple of (high_quality_profiles, low_quality_profiles)
        """
        if not profiles:
            return [], []

        high_quality = []
        low_quality = []

        for profile in profiles:
            score = self.calculate_quality_score(profile)
            profile['_quality_score'] = score

            if score >= min_quality_score:
                high_quality.append(profile)
            else:
                low_quality.append(profile)

        # Sort high quality profiles by score (highest first)
        high_quality.sort(key=lambda x: x['_quality_score'], reverse=True)

        return high_quality, low_quality

    def wait_with_early_termination(self,
                                  snapshot_id: str,
                                  company_pattern: str,
                                  case_sensitive: bool = False,
                                  min_quality_score: int = 4,  # Increased default threshold
                                  max_wait: int = 600,
                                  check_interval: int = 15,
                                  early_check_interval: int = 5) -> Optional[List[Dict]]:
        """
        Wait for job completion with early termination when high-quality matches are found

        Args:
            snapshot_id: The snapshot ID to wait for
            company_pattern: Regex pattern for company filtering
            case_sensitive: Whether regex should be case sensitive
            min_quality_score: Minimum score to trigger early termination (1-10 scale)
            max_wait: Maximum wait time in seconds
            check_interval: Normal check interval
            early_check_interval: Frequent check interval for early results

        Returns:
            List of matching profiles or None
        """
        start_time = time.time()
        print(f"⚡ Smart waiting with early termination enabled")
        print(f"   Target company pattern: '{company_pattern}'")
        print(f"   Minimum quality score for early termination: {min_quality_score}/10")
        print(f"   Early check interval: {early_check_interval}s")

        # Compile regex pattern
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(company_pattern, flags)
        except re.error as e:
            print(f"❌ Invalid regex pattern '{company_pattern}': {e}")
            return None

        attempts = 0
        best_matches = []

        # Phase 1: Frequent early checks (first 60 seconds)
        phase1_duration = 60
        while time.time() - start_time < min(phase1_duration, max_wait):
            attempts += 1
            elapsed = int(time.time() - start_time)

            print(f"🔍 Early check {attempts} ({elapsed}s) - Looking for quick matches...")

            partial_data, job_complete = self.check_partial_results(snapshot_id)

            if partial_data:
                print(f"📊 Found {len(partial_data)} profiles so far...")

                # Apply company filtering to partial results
                filtered_profiles = self.filter_profiles_by_company_regex(
                    partial_data, pattern, company_pattern
                )

                if filtered_profiles:
                    # Apply quality filtering
                    high_quality, low_quality = self.filter_quality_profiles(
                        filtered_profiles, min_quality_score=min_quality_score
                    )

                    print(f"📋 Quality Analysis: {len(high_quality)} high-quality, {len(low_quality)} low-quality")

                    if high_quality:
                        best_match = high_quality[0]  # Already sorted by score
                        print(f"⚡ HIGH QUALITY MATCH FOUND! Terminating early.")
                        print(f"   Name: {best_match.get('name', 'Unknown')}")
                        print(f"   Quality Score: {best_match['_quality_score']}/10")
                        current_company = best_match.get('current_company', {})
                        if isinstance(current_company, dict):
                            company_name = current_company.get('name', 'N/A')
                        else:
                            company_name = str(current_company) if current_company else 'N/A'
                        print(f"   Company: {company_name}")
                        print(f"   Time saved: ~{max_wait - elapsed} seconds")
                        return high_quality

                    # Keep track of any matches, even if not high quality yet
                    best_matches = filtered_profiles

            if job_complete:
                print(f"✅ Job completed during early phase!")
                if best_matches:
                    # Apply final quality filtering
                    high_quality, low_quality = self.filter_quality_profiles(best_matches)
                    return high_quality if high_quality else best_matches
                break

            time.sleep(early_check_interval)

        # Phase 2: Normal checking if no early termination
        if best_matches:
            print(f"📈 Continuing with normal checks (found {len(best_matches)} matches)")
        else:
            print(f"⏳ No early matches found, continuing with normal polling...")

        while time.time() - start_time < max_wait:
            attempts += 1
            elapsed = int(time.time() - start_time)

            url = f"{self.base_url}/snapshot/{snapshot_id}"
            params = {"format": "json"}

            try:
                response = requests.get(url, headers=self.headers, params=params)

                print(f"Attempt {attempts}: Status {response.status_code} ({elapsed}s elapsed)")

                if response.status_code == 200:
                    print(f"✅ Discovery job {snapshot_id} completed!")
                    data = response.json()

                    # Handle different response formats
                    if isinstance(data, list):
                        final_data = data
                    elif isinstance(data, dict):
                        if 'data' in data:
                            final_data = data['data']
                        elif 'results' in data:
                            final_data = data['results']
                        else:
                            final_data = [data]
                    else:
                        final_data = []

                    if final_data:
                        # Apply company filtering
                        filtered_results = self.filter_profiles_by_company_regex(
                            final_data, pattern, company_pattern
                        )

                        # Apply quality filtering
                        if filtered_results:
                            high_quality, low_quality = self.filter_quality_profiles(filtered_results)
                            return high_quality if high_quality else filtered_results

                        return filtered_results

                elif response.status_code == 202:
                    print(f"⏳ Job still processing...")
                else:
                    print(f"❌ Unexpected status: {response.status_code}")

            except Exception as e:
                print(f"⚠️ Error checking job status: {e}")

            time.sleep(check_interval)

        print(f"⏰ Timeout reached, returning best matches found so far")
        if best_matches:
            high_quality, low_quality = self.filter_quality_profiles(best_matches)
            return high_quality if high_quality else best_matches
        return None

    def filter_profiles_by_company_regex(self, profiles: List[Dict], pattern, pattern_str: str) -> List[Dict]:
        """
        Filter profiles using pre-compiled regex pattern
        """
        if not profiles:
            return []

        matched_profiles = []

        for profile in profiles:
            profile_matched = False
            match_details = []

            # Check current company
            current_company = profile.get('current_company', {})
            if isinstance(current_company, dict):
                current_company_name = current_company.get('name', '')
            else:
                current_company_name = str(current_company) if current_company else ''

            if not current_company_name:
                current_company_name = profile.get('current_company_name', '')

            if current_company_name and pattern.search(current_company_name):
                profile_matched = True
                match_details.append(f"Current: {current_company_name}")

            # Check experience companies
            experience = profile.get('experience', [])
            if isinstance(experience, list):
                for exp in experience:
                    if isinstance(exp, dict):
                        exp_company = exp.get('company', '')
                        if exp_company and pattern.search(exp_company):
                            profile_matched = True
                            match_details.append(f"Experience: {exp_company}")

            if profile_matched:
                profile['_company_matches'] = match_details
                matched_profiles.append(profile)

        return matched_profiles

    def display_results_analysis(self, all_results: List[Dict], high_quality: List[Dict], low_quality: List[Dict]):
        """
        Display detailed analysis of profile quality
        """
        print(f"\n📋 LINKEDIN PROFILE ANALYSIS")
        print("=" * 50)
        print(f"Total profiles found: {len(all_results)}")
        print(f"High-quality profiles: {len(high_quality)}")
        print(f"Low-quality/skeleton profiles: {len(low_quality)}")

        if high_quality:
            print(f"\n✅ HIGH-QUALITY PROFILES ({len(high_quality)} profiles)")
            print("-" * 40)

            for i, profile in enumerate(high_quality, 1):
                print(f"\n👤 PROFILE {i} (Quality Score: {profile['_quality_score']}/10):")
                print(f"   Name: {profile.get('name', 'N/A')}")

                # Current company
                current_company = profile.get('current_company', {})
                if isinstance(current_company, dict):
                    company_name = current_company.get('name', 'N/A')
                    position = current_company.get('title', 'N/A')
                else:
                    company_name = str(current_company) if current_company else 'N/A'
                    position = profile.get(

#!/usr/bin/env python3
"""
Standalone Airbnb Scraper Script
Usage: python standalone_scraper.py <airbnb_url>
Returns: JSON data with listing details and downloaded image paths
"""

import json
import sys
import os
import time
import urllib.request
from urllib.parse import urlparse
import hashlib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class StandaloneAirbnbScraper:
    def __init__(self, headless=True, media_dir="media/listings"):
        self.driver = None
        self.wait = None
        self.media_dir = media_dir
        self.setup_media_directory()
        self.setup_driver(headless)
        
    def setup_media_directory(self):
        """Create media directory structure if it doesn't exist"""
        os.makedirs(self.media_dir, exist_ok=True)
        os.makedirs(os.path.join(self.media_dir, 'listing_images'), exist_ok=True)
        os.makedirs(os.path.join(self.media_dir, 'host_images'), exist_ok=True)
        
    def setup_driver(self, headless=True):
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        
        # Server environment settings
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-features=TranslateUI")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Try different browser binaries
        possible_binaries = [
            "/usr/bin/chromium-browser",
            "/usr/lib64/chromium-browser/chromium-browser",
            "/usr/bin/chromium",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable"
        ]
        
        browser_found = False
        for binary in possible_binaries:
            try:
                if os.path.exists(binary):
                    chrome_options.binary_location = binary
                    browser_found = True
                    break
            except Exception:
                continue
                
        if not browser_found:
            raise Exception("No Chrome/Chromium browser found")
            
        try:
            # Try local chromedriver first
            if os.path.exists('/usr/local/bin/chromedriver'):
                service = Service('/usr/local/bin/chromedriver')
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                # Fallback to webdriver manager
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            raise Exception(f"Failed to initialize WebDriver: {e}")
            
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 10)

    def download_image(self, url, filename):
        """Download image from URL and save to local file"""
        if not url:
            return None
            
        try:
            # Create a hash-based filename to avoid duplicates
            url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
            file_extension = os.path.splitext(urlparse(url).path)[1] or '.jpg'
            
            full_filename = f"{filename}_{url_hash}{file_extension}"
            
            # Download the image
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    with open(full_filename, 'wb') as f:
                        f.write(response.read())
                    return full_filename
                        
        except Exception as e:
            print(f"Error downloading image {url}: {e}", file=sys.stderr)
            
        return None

    def extract_host_info(self):
        """Extract host information including photo download"""
        host_info = {
            'host_name': '',
            'host_id': '',
            'host_photo_url': '',
            'host_photo_path': ''
        }
        
        try:
            print("Starting host information extraction...", file=sys.stderr)
            
            # Try multiple selectors for host section
            host_selectors = [
                "//div[contains(text(), 'Hosted by')]//ancestor::div[3]",
                "//section[contains(@aria-labelledby, 'host')]",
                "//div[contains(@class, 'host')]",
            ]
            
            host_section = None
            for selector in host_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        host_section = elements[0]
                        print(f"Found host section with selector: {selector}", file=sys.stderr)
                        break
                except:
                    continue
            
            if host_section:
                # Extract host profile URL and ID
                try:
                    profile_link = host_section.find_element(By.XPATH, ".//a[contains(@href, '/users/show/')]")
                    profile_url = profile_link.get_attribute('href')
                    print(f"Found host profile URL: {profile_url}", file=sys.stderr)
                    
                    # Extract host ID from URL
                    import re
                    host_id_match = re.search(r'/users/show/(\d+)', profile_url)
                    if host_id_match:
                        host_info['host_id'] = host_id_match.group(1)
                        print(f"Extracted host ID: {host_info['host_id']}", file=sys.stderr)
                except Exception as e:
                    print(f"Could not extract host profile URL: {e}", file=sys.stderr)
                
                # Extract host photo
                try:
                    host_img = host_section.find_element(By.XPATH, ".//img")
                    host_photo_url = host_img.get_attribute('src')
                    host_info['host_photo_url'] = host_photo_url
                    print(f"Found host photo: {host_photo_url}", file=sys.stderr)
                    
                    # Download host image
                    if host_photo_url:
                        host_image_path = os.path.join(self.media_dir, 'host_images', f"host_{host_info['host_id']}")
                        downloaded_path = self.download_image(host_photo_url, host_image_path)
                        if downloaded_path:
                            host_info['host_photo_path'] = downloaded_path
                            
                except Exception as e:
                    print(f"Could not extract host photo: {e}", file=sys.stderr)
                
                print(f"Host found - Name: {host_info['host_name']}, ID: {host_info['host_id']}", file=sys.stderr)
                
                # Try to extract host name from page source if not found in elements
                if not host_info['host_name']:
                    try:
                        print("Trying page source extraction for host name...", file=sys.stderr)
                        page_source = self.driver.page_source
                        
                        # Look for host name patterns in page source
                        host_patterns = [
                            r'"host"[^}]*"displayName":"([^"]+)"',
                            r'"hostName":"([^"]+)"',
                            r'Hosted by ([^<]+)',
                        ]
                        
                        for pattern in host_patterns:
                            match = re.search(pattern, page_source, re.IGNORECASE)
                            if match:
                                host_info['host_name'] = match.group(1).strip()
                                print(f"Found host name in page source: {host_info['host_name']}", file=sys.stderr)
                                break
                                
                    except Exception as e:
                        print(f"Error extracting host name from page source: {e}", file=sys.stderr)
                        
                print(f"Final host extraction result - Name: '{host_info['host_name']}', ID: '{host_info['host_id']}'", file=sys.stderr)
        
        except Exception as e:
            print(f"Error extracting host info: {e}", file=sys.stderr)
            
        return host_info

    def scrape_listing(self, listing_url):
        """Scrape a single listing and return data with image downloads"""
        print(f"Scraping listing: {listing_url}", file=sys.stderr)
        
        try:
            self.driver.get(listing_url)
            time.sleep(3)
            
            # Initialize result data
            data = {
                'listing_url': listing_url,
                'title': '',
                'location': '',
                'property_type': '',
                'guests_capacity': '',
                'bedrooms': '',
                'bathrooms': '',
                'main_photo_url': '',
                'main_photo_path': '',
                'host_name': '',
                'host_id': '',
                'host_photo_url': '',
                'host_photo_path': '',
                'amenities': [],
                'description': '',
                'price_per_night': '',
                'rating': '',
                'review_count': ''
            }
            
            # Extract title
            try:
                title_element = self.wait.until(EC.presence_of_element_located((By.XPATH, "//h1")))
                data['title'] = title_element.text.strip()
            except:
                pass
                
            # Extract location using multiple strategies
            import re as _re
            from urllib.parse import parse_qs as _parse_qs

            location_extracted = False

            # Strategy 1: Page title — "Listing Title in City, Country - Airbnb"
            try:
                page_title = self.driver.title
                print(f"Page title: {page_title}", file=sys.stderr)
                title_match = _re.search(
                    r'\bin\s+([^|\u2013\u2014-].+?)(?:\s*[-\u2013\u2014|]\s*(?:Airbnb|vacation rental))',
                    page_title, _re.IGNORECASE
                )
                if title_match:
                    data['location'] = title_match.group(1).strip()
                    location_extracted = True
                    print(f"Location from title: {data['location']}", file=sys.stderr)
            except Exception as _e:
                print(f"Title location strategy failed: {_e}", file=sys.stderr)

            # Strategy 2: JSON-LD structured data in <script type="application/ld+json">
            if not location_extracted:
                try:
                    page_source = self.driver.page_source
                    json_ld_blocks = _re.findall(
                        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                        page_source, _re.DOTALL
                    )
                    for block in json_ld_blocks:
                        try:
                            ld = json.loads(block)
                            items = ld if isinstance(ld, list) else [ld]
                            for item in items:
                                addr = item.get('address') or (item.get('location') or {})
                                if isinstance(addr, dict):
                                    city    = addr.get('addressLocality', '')
                                    region  = addr.get('addressRegion', '')
                                    country = addr.get('addressCountry', '')
                                    parts   = [p for p in [city, region, country] if p]
                                    if parts:
                                        data['location'] = ', '.join(parts)
                                        location_extracted = True
                                        print(f"Location from JSON-LD: {data['location']}", file=sys.stderr)
                                        break
                                elif isinstance(addr, str) and addr:
                                    data['location'] = addr
                                    location_extracted = True
                                    print(f"Location from JSON-LD string: {data['location']}", file=sys.stderr)
                                    break
                            if location_extracted:
                                break
                        except Exception:
                            continue
                except Exception as _e:
                    print(f"JSON-LD location strategy failed: {_e}", file=sys.stderr)

            # Strategy 3: og:title meta tag — "Listing Title in City, Country | Airbnb"
            if not location_extracted:
                try:
                    og_title = self.driver.find_element(
                        By.XPATH, "//meta[@property='og:title']"
                    ).get_attribute('content')
                    if og_title:
                        og_match = _re.search(
                            r'\bin\s+([^|\u2013\u2014-].+?)(?:\s*[-\u2013\u2014|]|$)',
                            og_title, _re.IGNORECASE
                        )
                        if og_match:
                            data['location'] = og_match.group(1).strip()
                            location_extracted = True
                            print(f"Location from og:title: {data['location']}", file=sys.stderr)
                except Exception as _e:
                    print(f"og:title location strategy failed: {_e}", file=sys.stderr)

            # Strategy 4: Breadcrumb navigation links
            if not location_extracted:
                try:
                    breadcrumb_selectors = [
                        "//nav[@aria-label='Breadcrumb']//a",
                        "//ol[contains(@class,'breadcrumb')]//a",
                        "//div[contains(@data-testid,'breadcrumb')]//a",
                        "//nav//ol//li//a",
                    ]
                    for selector in breadcrumb_selectors:
                        crumbs = self.driver.find_elements(By.XPATH, selector)
                        texts = [c.text.strip() for c in crumbs if c.text.strip()]
                        if len(texts) >= 2:
                            data['location'] = texts[-1]
                            location_extracted = True
                            print(f"Location from breadcrumb: {data['location']}", file=sys.stderr)
                            break
                except Exception as _e:
                    print(f"Breadcrumb location strategy failed: {_e}", file=sys.stderr)

            # Strategy 5: Embedded JSON in page source — common Airbnb data keys
            if not location_extracted:
                try:
                    try:
                        _ = page_source
                    except NameError:
                        page_source = self.driver.page_source
                    location_patterns = [
                        r'"city"\s*:\s*"([^"]+)"',
                        r'"localized_city"\s*:\s*"([^"]+)"',
                        r'"location_title"\s*:\s*"([^"]+)"',
                        r'"public_address"\s*:\s*"([^"]+)"',
                        r'"pdp_map_tracking"\s*:[^}]*"city"\s*:\s*"([^"]+)"',
                    ]
                    for pattern in location_patterns:
                        match = _re.search(pattern, page_source, _re.IGNORECASE)
                        if match:
                            candidate = match.group(1).strip()
                            # Reject obviously wrong values (single chars, numbers only)
                            if len(candidate) > 2 and not candidate.isdigit():
                                data['location'] = candidate
                                location_extracted = True
                                print(f"Location from page source pattern: {data['location']}", file=sys.stderr)
                                break
                except Exception as _e:
                    print(f"Page source location strategy failed: {_e}", file=sys.stderr)

            # Strategy 6: URL query params (?location=... or ?query=...)
            if not location_extracted:
                try:
                    parsed_url = urlparse(listing_url)
                    params = _parse_qs(parsed_url.query)
                    for key in ('location', 'query', 'place'):
                        if key in params and params[key]:
                            data['location'] = params[key][0]
                            location_extracted = True
                            print(f"Location from URL param: {data['location']}", file=sys.stderr)
                            break
                except Exception as _e:
                    print(f"URL param location strategy failed: {_e}", file=sys.stderr)

            if not location_extracted:
                print("Warning: could not extract location with any strategy", file=sys.stderr)
                
            # Extract property details
            try:
                details_text = self.driver.find_element(By.XPATH, "//h1/following-sibling::div//span").text
                
                import re
                guests_match = re.search(r'(\d+)\s*guest', details_text, re.IGNORECASE)
                if guests_match:
                    data['guests_capacity'] = guests_match.group(1)
                    
                bedroom_match = re.search(r'(\d+)\s*bedroom', details_text, re.IGNORECASE)
                if bedroom_match:
                    data['bedrooms'] = bedroom_match.group(1)
                    
                bathroom_match = re.search(r'(\d+(?:\.\d+)?)\s*bath', details_text, re.IGNORECASE)
                if bathroom_match:
                    data['bathrooms'] = bathroom_match.group(1)
            except:
                pass
                
            # Extract main photo with multiple selectors
            main_photo_selectors = [
                "//img[contains(@class, 'i14idq7r')]",  # Original selector
                "//picture/img",  # Common pattern for main images
                "//div[contains(@class, 'media-photo')]/img",
                "//img[contains(@alt, 'photo')]",
                "//img[1]"  # First image as fallback
            ]
            
            try:
                main_photo_url = None
                for selector in main_photo_selectors:
                    try:
                        main_img = self.driver.find_element(By.XPATH, selector)
                        main_photo_url = main_img.get_attribute('src')
                        if main_photo_url and 'http' in main_photo_url:
                            break
                    except:
                        continue
                
                if main_photo_url:
                    data['main_photo_url'] = main_photo_url
                    print(f"Found main photo: {main_photo_url}", file=sys.stderr)
                    
                    # Download main image
                    listing_hash = hashlib.md5(listing_url.encode()).hexdigest()[:10]
                    main_image_path = os.path.join(self.media_dir, 'listing_images', f"listing_{listing_hash}")
                    downloaded_path = self.download_image(main_photo_url, main_image_path)
                    if downloaded_path:
                        data['main_photo_path'] = downloaded_path
                        print(f"Downloaded main photo to: {downloaded_path}", file=sys.stderr)
                        
            except Exception as e:
                print(f"Error extracting main photo: {e}", file=sys.stderr)
                
            # Extract host information
            host_info = self.extract_host_info()
            data.update(host_info)
            
            # Extract property type
            try:
                property_type_element = self.driver.find_element(By.XPATH, "//h1/following-sibling::div[1]")
                data['property_type'] = property_type_element.text.strip()
            except:
                pass
                
            # Extract amenities
            try:
                amenity_elements = self.driver.find_elements(By.XPATH, "//div[contains(text(), 'What this place offers')]/following-sibling::div//div[contains(@class, 'tw-text')]")
                data['amenities'] = [elem.text.strip() for elem in amenity_elements[:10]]
            except:
                pass
                
            # Extract description
            try:
                desc_element = self.driver.find_element(By.XPATH, "//h2[contains(text(), 'About')]/following-sibling::div//span")
                data['description'] = desc_element.text.strip()[:500]  # Limit to 500 chars
            except:
                pass
                
            return data
            
        except Exception as e:
            raise Exception(f"Scraping error: {str(e)}")
            
    def close(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()

def main():
    if len(sys.argv) != 2:
        print("Usage: python standalone_scraper.py <airbnb_url>", file=sys.stderr)
        sys.exit(1)
        
    airbnb_url = sys.argv[1]
    
    # Validate URL
    if 'airbnb.com' not in airbnb_url:
        print("Error: Please provide a valid Airbnb URL", file=sys.stderr)
        sys.exit(1)
        
    scraper = None
    try:
        # Create scraper instance
        scraper = StandaloneAirbnbScraper(headless=True)
        
        # Scrape the listing
        data = scraper.scrape_listing(airbnb_url)
        
        # Output JSON result
        print(json.dumps(data, indent=2))
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
        
    finally:
        if scraper:
            scraper.close()

if __name__ == "__main__":
    main()
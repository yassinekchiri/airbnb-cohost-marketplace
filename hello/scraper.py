import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from .models import AirbnbListing, DetailedAirbnbListing

class AirbnbScraper:
    def __init__(self, headless=True):
        self.driver = None
        self.wait = None
        self.setup_driver(headless)
        
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
                import os
                if os.path.exists(binary):
                    chrome_options.binary_location = binary
                    browser_found = True
                    break
            except:
                continue
        
        if not browser_found:
            raise Exception("No Chrome/Chromium browser found. Please install chromium or google-chrome.")
        
        try:
            # Try using manually installed ChromeDriver first
            import os
            if os.path.exists("/usr/local/bin/chromedriver"):
                service = Service("/usr/local/bin/chromedriver")
            else:
                # Fallback to ChromeDriverManager
                service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 15)
        except Exception as e:
            raise Exception(f"Failed to setup Chrome driver: {str(e)}")
    
    def search_listings(self, location="New York"):
        try:
            self.driver.get("https://www.airbnb.com")
            
            # Accept cookies if present
            try:
                cookie_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'OK') or contains(@data-testid, 'accept')]"))
                )
                cookie_button.click()
            except TimeoutException:
                pass  # No cookie banner
            
            # Find and fill the search box
            search_selectors = [
                "//input[@placeholder='Search destinations']",
                "//input[@data-testid='structured-search-input-field-query']",
                "//input[contains(@placeholder, 'Where')]",
                "//input[@name='query']"
            ]
            
            search_box = None
            for selector in search_selectors:
                try:
                    search_box = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    break
                except TimeoutException:
                    continue
            
            if not search_box:
                raise Exception("Could not find search input field")
            
            search_box.clear()
            search_box.send_keys(location)
            
            # Click search button
            search_selectors = [
                "//button[@type='submit']",
                "//button[contains(@data-testid, 'structured-search-input-search-button')]",
                "//button[contains(text(), 'Search')]"
            ]
            
            search_button = None
            for selector in search_selectors:
                try:
                    search_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    break
                except TimeoutException:
                    continue
            
            if search_button:
                search_button.click()
            else:
                # Try pressing Enter on search box
                from selenium.webdriver.common.keys import Keys
                search_box.send_keys(Keys.RETURN)
            
            # Wait for results to load
            time.sleep(5)
            return True
            
        except Exception as e:
            raise Exception(f"Error during search: {str(e)}")
    
    def scrape_listings(self, location, max_listings=10):
        listings_data = []
        
        try:
            # Wait for listings to load with multiple selectors
            listing_selectors = [
                "//div[@data-testid='card-container']",
                "//div[contains(@class, 'listing')]",
                "//div[@role='group']//a[contains(@href, '/rooms/')]"
            ]
            
            listing_elements = []
            for selector in listing_selectors:
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    listing_elements = self.driver.find_elements(By.XPATH, selector)
                    if listing_elements:
                        break
                except TimeoutException:
                    continue
            
            if not listing_elements:
                raise Exception("No listing elements found")
            
            # Scroll to load more listings
            for i in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
            
            # Re-find elements after scrolling
            listing_elements = self.driver.find_elements(By.XPATH, listing_selectors[0] if listing_elements else listing_selectors[1])
            
            for idx, listing in enumerate(listing_elements[:max_listings]):
                try:
                    listing_data = self.extract_listing_data(listing)
                    if listing_data:
                        listing_data['search_location'] = location
                        
                        # Save to database
                        AirbnbListing.objects.create(
                            title=listing_data.get('title', 'No title'),
                            location=listing_data.get('location', 'No location'),
                            price=listing_data.get('price', 'No price'),
                            rating=listing_data.get('rating', ''),
                            listing_url=listing_data.get('listing_url', ''),
                            image_url=listing_data.get('image_url', ''),
                            search_location=location
                        )
                        
                        listings_data.append(listing_data)
                        
                except Exception:
                    continue
            
            return listings_data
            
        except Exception as e:
            raise Exception(f"Error scraping listings: {str(e)}")
    
    def extract_listing_data(self, listing_element):
        data = {}
        
        try:
            # Multiple selectors for different Airbnb layouts
            title_selectors = [
                ".//div[@data-testid='listing-card-title']",
                ".//div[contains(@class, 'title')]//text()",
                ".//h3",
                ".//div[contains(@class, 't1jojoys')]"
            ]
            
            for selector in title_selectors:
                try:
                    title_element = listing_element.find_element(By.XPATH, selector)
                    data["title"] = title_element.text.strip()
                    if data["title"]:
                        break
                except:
                    continue
            
            if not data.get("title"):
                data["title"] = "No title found"
            
            # Price
            price_selectors = [
                ".//span[contains(text(), '$')]",
                ".//div[contains(@class, 'price')]",
                ".//span[@aria-label and contains(@aria-label, '$')]"
            ]
            
            for selector in price_selectors:
                try:
                    price_element = listing_element.find_element(By.XPATH, selector)
                    price_text = price_element.text.strip()
                    if '$' in price_text:
                        data["price"] = price_text
                        break
                except:
                    continue
            
            if not data.get("price"):
                data["price"] = "No price found"
            
            # Rating
            rating_selectors = [
                ".//span[contains(@aria-label, 'rating')]",
                ".//div[contains(@class, 'rating')]",
                ".//span[contains(text(), '★')]"
            ]
            
            for selector in rating_selectors:
                try:
                    rating_element = listing_element.find_element(By.XPATH, selector)
                    rating_text = rating_element.get_attribute("aria-label") or rating_element.text
                    if rating_text:
                        data["rating"] = rating_text.strip()
                        break
                except:
                    continue
            
            if not data.get("rating"):
                data["rating"] = "No rating found"
            
            # Location/subtitle
            location_selectors = [
                ".//div[@data-testid='listing-card-subtitle']",
                ".//div[contains(@class, 'subtitle')]",
                ".//div[contains(@class, 'location')]"
            ]
            
            for selector in location_selectors:
                try:
                    location_element = listing_element.find_element(By.XPATH, selector)
                    data["location"] = location_element.text.strip()
                    if data["location"]:
                        break
                except:
                    continue
            
            if not data.get("location"):
                data["location"] = "No location found"
            
            # Image URL - try multiple approaches to get high quality images
            try:
                # Try to find the main listing image
                img_selectors = [
                    ".//img[contains(@data-testid, 'picture')]",
                    ".//img[@data-original-uri]",
                    ".//img[contains(@class, 'itu7ddv')]",
                    ".//div[contains(@class, '_1h6us9g')]//img",
                    ".//picture//img",
                    ".//img"
                ]
                
                best_image_url = ""
                for selector in img_selectors:
                    try:
                        img_elements = listing_element.find_elements(By.XPATH, selector)
                        for img in img_elements:
                            # Get various image URL attributes
                            src = img.get_attribute("src") or ""
                            data_src = img.get_attribute("data-src") or ""
                            data_original = img.get_attribute("data-original-uri") or ""
                            
                            # Prefer higher resolution images
                            for url in [data_original, data_src, src]:
                                if url and ("jpg" in url or "jpeg" in url or "png" in url or "webp" in url):
                                    # Skip placeholder/loading images
                                    if not any(skip in url.lower() for skip in ["loading", "placeholder", "blank", "1x1"]):
                                        # Prefer larger images (look for size indicators)
                                        if any(size in url for size in ["720", "960", "1200", "large"]) or not best_image_url:
                                            best_image_url = url
                                            break
                            if best_image_url:
                                break
                        if best_image_url:
                            break
                    except:
                        continue
                
                data["image_url"] = best_image_url
            except:
                data["image_url"] = ""
            
            # Link to listing
            try:
                link_element = listing_element.find_element(By.TAG_NAME, "a")
                href = link_element.get_attribute("href")
                if href and not href.startswith("http"):
                    href = "https://www.airbnb.com" + href
                data["listing_url"] = href or ""
            except:
                data["listing_url"] = ""
            
            return data
            
        except Exception:
            return None
    
    def close(self):
        if self.driver:
            self.driver.quit()
    
    def scrape_airbnb_search(self, location, max_listings=10):
        try:
            if not self.search_listings(location):
                raise Exception("Failed to search listings")
            
            listings = self.scrape_listings(location, max_listings)
            return listings
            
        except Exception as e:
            raise Exception(f"Scraping failed: {str(e)}")
        finally:
            self.close()

    def scrape_detailed_listing(self, listing_url):
        try:
            print(f"Scraping detailed listing: {listing_url}")
            self.driver.get(listing_url)
            
            # Wait for page to load
            time.sleep(5)
            
            # Initialize data dictionary
            data = {
                'listing_url': listing_url,
                'title': '',
                'main_photo_url': '',
                'host_name': '',
                'host_id': '',
                'host_profile_url': '',
                'host_photo_url': '',
                'host_verified': False,
                'host_superhost': False,
                'host_years_hosting': '',
                'host_reviews_count': '',
                'host_response_rate': '',
                'host_response_time': '',
                'host_languages': '',
                'host_description': '',
                'host_location': '',
                'host_joined_date': '',
                'property_type': '',
                'location': '',
                'guests_capacity': '',
                'bedrooms': '',
                'bathrooms': ''
            }
            
            # Extract title
            title_selectors = [
                "//h1[contains(@class, 'hpipapi')]",
                "//h1[@data-testid='listing-title']",
                "//h1",
                "//*[contains(@class, 'listing-title')]"
            ]
            
            for selector in title_selectors:
                try:
                    title_element = self.driver.find_element(By.XPATH, selector)
                    data['title'] = title_element.text.strip()
                    if data['title']:
                        break
                except:
                    continue
            
            # Extract main photo
            photo_selectors = [
                "//img[contains(@class, '_6tbg2q')]",
                "//div[contains(@class, '_1h6us9g')]//img",
                "//picture//img[@src]",
                "//img[contains(@alt, 'listing')]",
                "//div[contains(@data-testid, 'photo-viewer')]//img"
            ]
            
            for selector in photo_selectors:
                try:
                    photo_elements = self.driver.find_elements(By.XPATH, selector)
                    for img in photo_elements:
                        src = img.get_attribute("src") or ""
                        if src and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']) and 'placeholder' not in src.lower():
                            data['main_photo_url'] = src
                            break
                    if data['main_photo_url']:
                        break
                except:
                    continue
            
            # Extract host information with multiple strategies
            print("Starting host information extraction...")
            
            # Strategy 1: Look for host section with multiple selectors
            host_section_selectors = [
                "//div[contains(@data-testid, 'host-profile')]",
                "//div[contains(text(), 'Hosted by')]//ancestor::div[3]",
                "//section[contains(@aria-labelledby, 'host')]", 
                "//div[contains(@class, 'host-section')]",
                "//h2[contains(text(), 'Hosted by')]//parent::div//parent::div",
                "//div[contains(@class, 'Avatar')]//parent::div//parent::div",
                "//img[contains(@alt, 'Host')]//ancestor::div[3]"
            ]
            
            host_section = None
            for selector in host_section_selectors:
                try:
                    host_section = self.driver.find_element(By.XPATH, selector)
                    print(f"Found host section with selector: {selector}")
                    break
                except:
                    continue
            
            # Strategy 2: Direct search for host elements across entire page
            if not host_section:
                print("No host section found, searching entire page...")
                
            # Extract host name with comprehensive selectors
            host_name_selectors = [
                "//h2[contains(text(), 'Hosted by')]",
                "//div[contains(text(), 'Hosted by')]",
                "//span[contains(text(), 'Hosted by')]",
                "//h3[contains(text(), 'Meet your Host')]//following::h1[1]",
                "//div[contains(@class, 'host')]//h2",
                "//a[contains(@href, '/users/show/')]//span",
                "//a[contains(@href, '/users/show/')]",
                "//img[contains(@alt, 'Host')]//following::div//span[1]",
                "//*[contains(@class, 'host-name')]",
                "//*[text()[contains(., 'Hosted by')]]"
            ]
            
            for selector in host_name_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text:
                            if 'Hosted by' in text:
                                # Extract name after "Hosted by"
                                name = text.replace('Hosted by', '').strip()
                                if name and len(name) > 1:
                                    data['host_name'] = name
                                    print(f"Found host name: {name}")
                                    break
                            elif len(text) > 1 and len(text) < 50:  # Reasonable name length
                                data['host_name'] = text
                                print(f"Found host name: {text}")
                                break
                    if data['host_name']:
                        break
                except Exception as e:
                    print(f"Error with selector {selector}: {e}")
                    continue
            
            # Extract host profile URL and ID
            host_url_selectors = [
                "//a[contains(@href, '/users/show/')]",
                "//a[contains(@href, '/user/')]",
                "//img[contains(@alt, 'Host')]//parent::a",
                "//div[contains(text(), 'Hosted by')]//a",
                "//h2[contains(text(), 'Hosted by')]//a"
            ]
            
            for selector in host_url_selectors:
                try:
                    host_links = self.driver.find_elements(By.XPATH, selector)
                    for link in host_links:
                        href = link.get_attribute("href")
                        if href:
                            if not href.startswith("http"):
                                href = "https://www.airbnb.com" + href
                            data['host_profile_url'] = href
                            print(f"Found host profile URL: {href}")
                            
                            # Extract host ID from URL
                            import re
                            id_match = re.search(r'/users/show/(\d+)', href)
                            if id_match:
                                data['host_id'] = id_match.group(1)
                                print(f"Extracted host ID: {data['host_id']}")
                            break
                    if data['host_profile_url']:
                        break
                except Exception as e:
                    print(f"Error extracting host URL: {e}")
                    continue
            
            # Extract host photo
            host_photo_selectors = [
                "//img[contains(@alt, 'Host')]",
                "//img[contains(@alt, 'host')]", 
                "//div[contains(@class, 'Avatar')]//img",
                "//a[contains(@href, '/users/show/')]//img"
            ]
            
            for selector in host_photo_selectors:
                try:
                    photo_elements = self.driver.find_elements(By.XPATH, selector)
                    for photo in photo_elements:
                        src = photo.get_attribute("src")
                        if src and 'user' in src.lower():
                            data['host_photo_url'] = src
                            print(f"Found host photo: {src}")
                            break
                    if data['host_photo_url']:
                        break
                except:
                    continue
            
            # If we found host information, look for additional details in the context
            if data['host_name'] or data['host_profile_url']:
                print(f"Host found - Name: {data['host_name']}, ID: {data['host_id']}")
                
                # Look for host section context for additional info
                if host_section:
                    # Host verification and superhost status
                    verification_text = host_section.text.lower()
                    data['host_verified'] = 'verified' in verification_text or 'identity verified' in verification_text
                    data['host_superhost'] = 'superhost' in verification_text
                else:
                    # Search entire page for verification status
                    page_text = self.driver.page_source.lower()
                    data['host_verified'] = 'verified' in page_text or 'identity verified' in page_text
                    data['host_superhost'] = 'superhost' in page_text
            
            # Additional fallback: search page source for host information if not found
            if not data['host_name']:
                print("Trying page source extraction for host name...")
                page_source = self.driver.page_source
                
                # Look for "Hosted by" pattern in page source
                import re
                hosted_by_patterns = [
                    r'Hosted by ([^"<>]{2,40})',
                    r'"host_name":"([^"]{2,40})"',
                    r'Meet your Host[^>]*>([^<]{2,40})<',
                    r'/users/show/(\d+)[^>]*>([^<]{2,40})<'
                ]
                
                for pattern in hosted_by_patterns:
                    matches = re.findall(pattern, page_source, re.IGNORECASE)
                    if matches:
                        if isinstance(matches[0], tuple):
                            # Pattern returns both ID and name
                            if len(matches[0]) == 2:
                                data['host_id'] = matches[0][0]
                                data['host_name'] = matches[0][1].strip()
                            else:
                                data['host_name'] = matches[0][0].strip()
                        else:
                            data['host_name'] = matches[0].strip()
                        print(f"Found host name in page source: {data['host_name']}")
                        break
                
                # Look for host ID in URLs
                if not data['host_id']:
                    url_patterns = [
                        r'/users/show/(\d+)',
                        r'"host_id":"(\d+)"',
                        r'user_id["\s]*:[\s"]*(\d+)'
                    ]
                    
                    for pattern in url_patterns:
                        matches = re.findall(pattern, page_source)
                        if matches:
                            data['host_id'] = matches[0]
                            print(f"Found host ID in page source: {data['host_id']}")
                            break
            
            print(f"Final host extraction result - Name: '{data['host_name']}', ID: '{data['host_id']}'")
            
            # Continue with the rest of the host information extraction only if we have basic info
            if data['host_name'] or data['host_profile_url'] or data['host_id']:
                # Look for host section context for additional info  
                
                # Extract host stats (years hosting, reviews, response rate, etc.)
                stats_elements = host_section.find_elements(By.XPATH, ".//div[contains(@class, 'review') or contains(@class, 'stat') or contains(text(), 'year') or contains(text(), 'review') or contains(text(), '%') or contains(text(), 'language') or contains(text(), 'joined')]")
                
                for stat in stats_elements:
                    stat_text = stat.text.lower()
                    if 'year' in stat_text and 'hosting' in stat_text:
                        data['host_years_hosting'] = stat.text
                    elif 'review' in stat_text and any(char.isdigit() for char in stat_text):
                        data['host_reviews_count'] = stat.text
                    elif '%' in stat_text and 'response' in stat_text:
                        data['host_response_rate'] = stat.text
                    elif ('minute' in stat_text or 'hour' in stat_text) and 'response' in stat_text:
                        data['host_response_time'] = stat.text
                    elif 'language' in stat_text:
                        data['host_languages'] = stat.text
                    elif 'joined' in stat_text:
                        data['host_joined_date'] = stat.text
                
                # Extract host description
                description_selectors = [
                    ".//div[contains(@class, 'host-about')]",
                    ".//div[contains(@class, 'description')]",
                    ".//p[contains(@class, 'about')]"
                ]
                
                for selector in description_selectors:
                    try:
                        desc_element = host_section.find_element(By.XPATH, selector)
                        desc_text = desc_element.text.strip()
                        if len(desc_text) > 20:  # Only take substantial descriptions
                            data['host_description'] = desc_text[:500]  # Limit length
                            break
                    except:
                        continue
                
                # Extract host location
                location_selectors = [
                    ".//div[contains(text(), 'Lives in')]",
                    ".//div[contains(text(), 'From')]",
                    ".//span[contains(@class, 'location')]"
                ]
                
                for selector in location_selectors:
                    try:
                        location_element = host_section.find_element(By.XPATH, selector)
                        location_text = location_element.text.strip()
                        if 'Lives in' in location_text:
                            data['host_location'] = location_text.replace('Lives in', '').strip()
                        elif 'From' in location_text:
                            data['host_location'] = location_text.replace('From', '').strip()
                        else:
                            data['host_location'] = location_text
                        if data['host_location']:
                            break
                    except:
                        continue
            
            
            # Extract property details
            details_selectors = [
                "//div[contains(@class, 'property-detail')]",
                "//div[contains(text(), 'guests')]//parent::div",
                "//span[contains(text(), 'bedroom')]//parent::div//parent::div",
                "//div[contains(@class, 'overview-info')]"
            ]
            
            for selector in details_selectors:
                try:
                    details_section = self.driver.find_element(By.XPATH, selector)
                    details_text = details_section.text.lower()
                    
                    # Extract capacity, bedrooms, bathrooms
                    import re
                    
                    guests_match = re.search(r'(\d+)\s*guests?', details_text)
                    if guests_match:
                        data['guests_capacity'] = guests_match.group(0)
                    
                    bedrooms_match = re.search(r'(\d+)\s*bedrooms?', details_text)
                    if bedrooms_match:
                        data['bedrooms'] = bedrooms_match.group(0)
                    
                    bathrooms_match = re.search(r'(\d+(?:\.\d+)?)\s*bathrooms?', details_text)
                    if bathrooms_match:
                        data['bathrooms'] = bathrooms_match.group(0)
                    
                    break
                except:
                    continue
            
            # Extract location
            location_selectors = [
                "//div[contains(@class, 'location')]//span",
                "//button[contains(@aria-label, 'location')]",
                "//div[contains(@data-testid, 'location')]"
            ]
            
            for selector in location_selectors:
                try:
                    location_element = self.driver.find_element(By.XPATH, selector)
                    data['location'] = location_element.text.strip()
                    if data['location']:
                        break
                except:
                    continue
            
            # Extract property type
            type_selectors = [
                "//div[contains(text(), 'Entire')]",
                "//div[contains(text(), 'Private')]",
                "//div[contains(text(), 'Shared')]",
                "//h2[contains(@class, 'property-type')]"
            ]
            
            for selector in type_selectors:
                try:
                    type_element = self.driver.find_element(By.XPATH, selector)
                    type_text = type_element.text.strip()
                    if any(word in type_text.lower() for word in ['entire', 'private', 'shared', 'apartment', 'house', 'room']):
                        data['property_type'] = type_text
                        break
                except:
                    continue
            
            return data
            
        except Exception as e:
            raise Exception(f"Failed to scrape detailed listing: {str(e)}")

def scrape_airbnb_listings(location, max_listings=10, headless=True):
    scraper = AirbnbScraper(headless=headless)
    try:
        return scraper.scrape_airbnb_search(location, max_listings)
    except Exception as e:
        scraper.close()
        raise e

def scrape_single_airbnb_listing(listing_url, headless=True):
    scraper = AirbnbScraper(headless=headless)
    try:
        detailed_data = scraper.scrape_detailed_listing(listing_url)
        
        # Save to database
        listing, created = DetailedAirbnbListing.objects.update_or_create(
            listing_url=listing_url,
            defaults=detailed_data
        )
        
        return detailed_data
    except Exception as e:
        raise e
    finally:
        scraper.close()
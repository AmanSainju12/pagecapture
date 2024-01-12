import io
import math
import os
import shutil
import time
import subprocess

from PIL import Image
from selenium import webdriver

from . import browser_options
from .utils.helper import ScreenshotHelper
from wa.core.logging.logger import StandardOutLoggingHandler

log = StandardOutLoggingHandler("wa.browser_handler").get_logger()


class BrowserHandler:
    """
        This object is essentially just a wrapper for the Selenium webdriver object. We customize the browser sessions
        so that we obfuscate as much as possible, though direct access to the webdriver is still available.

        We make one loose assumption here, which is that we set the profile location to a temp directory of our choosing
        if the user did not specify one in the kwargs submitted. We track this location because we want to stay tidy
        and remove the location when we're done using it.

        :param executable_path
            - Full path location of the browser's 'driver'. Selenium uses specific drivers for browser.
                Reference Selenium documentation on what driver to use:
                https://github.com/SeleniumHQ/selenium/tree/master/py

        :param browser_type
            - lowercase string to identify the browser that should be used
            - Accepted Values: chrome, firefox

        :param kwargs:
            - Any remaining kwargs will get passed on to the browser profile creation process

            :key proxy_settings
            :val Selenium Proxy object
                - Reference: https://github.com/SeleniumHQ/selenium/blob/master/py/selenium/webdriver/common/proxy.py

            :key firefox_binary
            :val String to Firefox browser binary

    """

    def __init__(self, GECKO_DRIVER_LOG='/var/log/bmp/geckodriver.log', executable_path=None, browser_type='firefox',
                 **kwargs):
        self.browser_type = browser_type
        self.executable_path = executable_path
        self.GECKO_DRIVER_LOG = GECKO_DRIVER_LOG
        self.browser_profile = self._create_browser_profile(**kwargs)
        if kwargs.get('persistent_session_cookie'):
            self.browser_profile_loc = kwargs.get('profile_dir_start_mc')
        else:
            self.browser_profile_loc = self.browser_profile.profile_dir
        self.har_export_plugin_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                                   "lib", "har_export_trigger-0.6.1-an+fx.xpi")
        self.kwargs = kwargs

    def create_webdriver(self, seconds=60, **kwargs):
        self.webdriver = self._create_webdriver(**kwargs)
        self.set_page_timeout(seconds)
        self.name = '{}_webdriver'.format(self.browser_type)

    # Private
    def _create_webdriver(self, **kwargs):
        """
        Creates a Selenium Webdriver depending on the specified browser type.

        :param browser_profile:
            - Should be created by _create_browser_profile method
        """
        if 'chrome' in self.browser_type:
            return webdriver.Chrome(executable_path=self.executable_path, chrome_options=self.browser_profile)
        if 'firefox' in self.browser_type:
            options = None

            if 'dev_tools' in kwargs and kwargs['dev_tools']:
                # Enable and open the firefox development tools
                options = webdriver.FirefoxOptions()
                options.add_argument("--devtools")

            # WA-8069: Create webdriver with the browser profile created in the StartMyCrawl
            if 'persistent_session_cookie' in kwargs and kwargs.get('persistent_session_cookie'):
                log.info(f"Creating webdriver for persistent session cookie crawl.")
                wd = webdriver.Firefox(options=self.browser_profile,
                                       firefox_binary=kwargs.get('firefox_binary'),
                                       executable_path=self.executable_path, log_path=self.GECKO_DRIVER_LOG)
            else:
                wd = webdriver.Firefox(firefox_options=options,
                                       firefox_profile=self.browser_profile,
                                       firefox_binary=kwargs.get('firefox_binary'),
                                       executable_path=self.executable_path, log_path=self.GECKO_DRIVER_LOG)

            return self._load_har_export_plugin(wd, **kwargs)

    # Private
    def _create_browser_profile(self, **kwargs):
        """
        Creates a profile object depending on the specified browser type

        :param kwargs:
            - Reference browser_options.py for relevant passable kwargs
        """
        if 'chrome' in self.browser_type:
            return browser_options.create_chrome_options(**kwargs)
        if 'firefox' in self.browser_type:
            return browser_options.create_firefox_options(**kwargs)
        return None

    def set_page_timeout(self, seconds=60):
        """
        Method will set the number of seconds the webdriver will wait for the page to load.

        :param seconds:
            - Default value of 60 seconds unless otherwise submitted
        """
        if self.webdriver is None:
            raise TypeError("Webdriver object does not exist.")
        self.webdriver.set_page_load_timeout(seconds)

    def execute_script(self, script, *args):
        """
        Executes a synchronous javascript command to the browser, returns results, if any.

        :param script:
            - Javascript to be executed in the console

        :param args:
            - Any arguments needed for the script

        :return:
            - Result from webdriver.get() function
            - None if webdriver object doesn't exist
        """
        if self.webdriver is None:
            raise TypeError("Webdriver object doesn't exist")
        return self.webdriver.execute_script(script, *args)

    def execute_async_script(self, script, *args):
        """
         Executes a synchronous javascript command to the browser, returns results, if any.

         :param script:
             - Javascript to be executed in the console

         :param args:
             - Any arguments needed for the script

         :return:
             - Result from webdriver.get() function
             - None if webdriver object doesn't exist
         """
        if self.webdriver is None:
            raise TypeError("Webdriver object doesn't exist.")
        return self.webdriver.execute_aysnc_script(script, *args)

    def _browser_wait(self, delay=0):
        """
        This uses the implicitly_wait() setting in Selenium to force the browser into a 'wait' state that
        does not break the connection between Selenium, the driver, and the browser. We set the wait time,
        in seconds, make a purposefully fake element search and return from the search. The entire duration
        last as long as the value that we set.

        :param delay : (int)
            - Number of seconds that webdriver.implicitly_wait() is set.
        :return:
            - Nothing
        """
        if self.webdriver:
            self.webdriver.implicitly_wait(delay)
            try:
                self.webdriver.find_element_by_id("dummy-element-lookup")
            except:
                pass
            self.webdriver.implicitly_wait(0)

        return

    def __get_actual_height(self):
        """
        Calculates the maximum height for the page.
        It checks the document height(html) and body height and returns the highest
        one of them

        Returns: (int)
            - Returns highest found height of the page
        """
        max_body_height = int(self.execute_script('return document.body.scrollHeight'))
        log.info(f"Found max body height {max_body_height}")

        max_document_height = int(
            self.execute_script('return document.documentElement.scrollHeight'))
        log.info(f"GAH:: Found max document height: {max_document_height}")

        max_height = max([max_body_height, max_document_height])
        log.info(f"GAH:: Used max height: {max_height}")

        return max_height

    def get_max_height(self, df_ht: int = 0, delay: int = 5) -> int:
        """Get Max Height

        We are attempting to get the max height of the page. It seems
        that for this version of firefox we need to resize the window.
        By doing so it forces a re-calculation of the window height.
        After the resize the height is more accurate than the first time
        we ask.

        :param df_ht : (int)
            - The default height to use if javascript returns a zero height
        :param delay : (int)
            - Number of seconds to wait
        :return:
            - int, the max height of the page
        """
        max_height = 0
        calculation_times = 5
        calculation_count = 0

        while calculation_count < calculation_times:
            previous_max_height = self.__get_actual_height()
            log.info(f'GMH:: prev height found: {max_height}')

            self.webdriver.execute_script("window.scrollTo(0, {0})".format(previous_max_height))
            time.sleep(delay)

            new_max_height = self.__get_actual_height()
            log.info(f'GMH:: new height found: {max_height}')

            # break if new max height is equal to previous height
            if new_max_height == previous_max_height:
                # finally assigning max height
                max_height = new_max_height
                break
            calculation_count += 1

        # Only consider df_ht if  vertical dimension from the browser is 0 due to some issue.
        if max_height == 0:
            max_height = df_ht

        return max_height

    def get_screenshot(self, full=False, df_wd=980, df_ht=1000, default_height=22000,
                       maximum_length_image=600000, debug=False, screenshot_delay=5):
        """
            Retrieves the full page Screen shot or screenshot based on height(df_ht) defined by user when full is false .
            returns as png data. Uses a selenium feature where you submit javascript to the browser's Console.

            :param full : (boolean)
                   - Takes the full Screen shot  when  true. When false takes the screen  as per df_ht value.
            :param df_wd : (int)
                   - Width specified by user for the screens hot.
            :param df_ht : (int)
                   - Height specified by user for the screenshot. Will be honored only if the 'full' is False.
            :param default_height : (int)
                   - Is height  above which scroll cut and merge algorithm is required .
            :param maximum_length_image : (int)
                    - Is maximum length where scroll and cut loop breaks.
            :param debug : (bool)
                    - Pass in True if you want debug statements
            :param screenshot_delay: (int)
                    - Wait before interaction with the selenium
            :return:
                - png data, which should come back as binary
        """
        if self.webdriver is None:
            raise TypeError("Webdriver object doesn't exist")

        png_ss = None

        # Changing the input names to make more semantic sense for now
        user_wd = df_wd
        user_ht = df_ht
        cut_merge_threshold = default_height
        cut_merge_maximum_length_image = maximum_length_image

        try:
            # Always respect the horizontal dimension from the user input or defaults.
            max_width = user_wd
            if full:
                if debug:
                    log.info('GS:: Taking full Screen shot')

                # get max height
                max_height = self.get_max_height(user_ht, screenshot_delay)

                # Check for screenshot type and call the method corresponding to the method of screenshot capture
                sc_capture_type = self.kwargs.get('sc_capture_type', 1)
                crawl_ss_type = self.kwargs.get('crawl_ss_type', sc_capture_type)
                if crawl_ss_type == sc_capture_type:
                    if max_height <= cut_merge_threshold:
                        if debug:
                            log.info(f"GS:: Using Single Screenshot Capture for height {max_height}")

                        # adding the window height difference to max height so that we can set up the viewport of
                        # actual page height
                        window_height = max_height + self.webdriver.execute_script(
                            "return window.outerHeight - window.innerHeight")

                        # setting the window height with calculated height
                        self.webdriver.set_window_size(max_width, window_height)
                        if debug:
                            log.info(f"GS:: Telling the driver to set window size to {max_width}x{window_height}")

                        # Some web pages are not being loaded without the initial scroll, so we are scrolling to the
                        # bottom of the page and scrolling back to the top to take the screenshot.
                        # Reference : https://smarsh.atlassian.net/browse/WA-4020
                        self.webdriver.execute_script("window.scrollTo({0}, {1})".format(max_width, max_height))
                        time.sleep(screenshot_delay)

                        self.webdriver.execute_script("window.scrollTo(0, 0)")
                        time.sleep(screenshot_delay)

                        # Takes screenshot
                        png_ss = self.webdriver.get_screenshot_as_png()
                    else:
                        if debug:
                            log.info(f"GS:: Using Cut & Merge as Max Height {max_height} "
                                     f"exceeds the threshold {cut_merge_threshold}")
                        png_ss = self.__get_screenshot_using_cut_and_merger(max_width, screenshot_delay, debug)

                else:
                    if debug:
                        log.info(f"Using screenshot capture with automation for height {max_height}")
                    png_ss = self.__get_screenshot_using_automation(cut_merge_maximum_length_image, max_height,
                                                                    max_width, screenshot_delay,
                                                                    debug)

            else:
                if debug:
                    log.info('GS:: Taking customized height screen shot as given by the user')
                # respect the height given by the user
                max_height = user_ht
                self.webdriver.set_window_size(max_width, max_height)
                time.sleep(screenshot_delay)
                png_ss = self.webdriver.get_screenshot_as_png()

        except Exception as e:
            import traceback
            traceback.print_exc()
            log.error(f"Error capturing screenshot: {e}")
            return png_ss

        if not ScreenshotHelper.is_valid_screenshot(png_ss, 1000):
            raise TypeError('Received an empty Screen shot object when content was expected.')

        return png_ss

    def __get_screenshot_using_cut_and_merger(self, max_width, screenshot_delay, debug=False):
        """
            This function scrolls the page  and takes screenshots at every instance of the  scroll and merges all the
            Screenshots taken in memory vertically until it meets the scroll height maximum_length_image or max_height
             whichever is the smaller.

                :param max_width : (int)
                       - width specified by user for the screens hot.
                :param screenshot_delay : (int)
                        - delay used between scroll calls to allow for refreshing of the page
                :param debug : (bool)
                       - set to true for debug output
                :return:
                    - png data, which should come back as binary           """

        slices = []
        offset = 0
        scroll_x = 0
        # defining the default window height to 15000 so that the screenshot shot chunk can be exact
        window_height = 15000
        ss_count = 0

        # get total page height
        max_height = self.get_max_height()
        if debug:
            log.info(f"CM:: Found new max height {max_height}")

        # maximum possible full screenshot of viewport of defined window height
        max_ss_count = math.floor(max_height / window_height)
        if debug:
            log.info(f"CM:: Possible screenshot {max_ss_count}")

        # adding the window height difference to max height so that we can set up the viewport of
        # actual page height
        new_window_height = window_height + self.webdriver.execute_script(
            "return window.outerHeight - window.innerHeight")
        if debug:
            log.info(f"CM:: Found new window height {new_window_height}")

        self.webdriver.set_window_size(max_width, new_window_height)
        if debug:
            log.info(f"CM:: Telling the driver to set the window size to {max_width}x{new_window_height}")

        while ss_count < max_ss_count:
            if debug:
                log.info(f"CM:: Screenshot count {ss_count}")

                # Setting the window to the appropriate offset
            self.webdriver.execute_script("window.scrollTo({0}, {1})".format(scroll_x, offset))
            if debug:
                log.info(f"CM:: Scrolling to {scroll_x}x{offset}")

            # waiting for a while after scrolling to the position
            time.sleep(screenshot_delay)

            img = Image.open(io.BytesIO(self.webdriver.get_screenshot_as_png()))

            # always get the offset from the image height to get the next position for accuracy
            offset += img.size[1]

            if debug:
                log.info(f"CM:: New offset position {offset}")

            slices.append(img)
            ss_count += 1

        # check and capture last screenshot if available
        last_image = self.capture_remaining_section(slices, max_height, max_width, window_height, scroll_x,
                                                    screenshot_delay, debug)
        if last_image:
            slices.append(last_image)

        width = [int(max_width)]
        png_ss = ScreenshotHelper.get_combined_screenshot(slices, width, offset)
        return png_ss

    def __get_screenshot_using_automation(self, maximum_length_image, max_height,
                                          max_width, screenshot_delay, debug=False):
        """
            This function scrolls the page until it meets the scroll height maximum_length_image or max_height
             whichever is the smaller.

                :param maximum_length_image : (int)
                        - Is maximum length where scroll and cut loop breaks.
                :param max_height : (int)
                       - document.body.scrollHeight .
                :param max_width : (int)
                       - width specified by user for the screens hot.
                :param screenshot_delay : (int)
                        - delay used between scroll calls to allow for refreshing of the page
                :param debug : (bool)
                       - set to true for debug output
                :return:
                    - png data, which should come back as binary
            """
        # Override the max_height with maximum_length_image if configured maximum_length_image is lesser
        if maximum_length_image < max_height:
            max_height = maximum_length_image
            log.info(f"CM:: Changing the Max Height to the Max Image Length {max_height}")
        else:
            log.info(f"CM:: Keeping the Max Height to the Max Image Length {max_height}")

        offset = 0
        scroll_x = 0
        orig_page_y_offset = None

        # Take the window height to add to the offset
        # Ref: https://stackoverflow.com/questions/1248081/how-to-get-the-browser-viewport-dimensions
        view_port_height = self.webdriver.execute_script(
            "return Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);")

        while offset < max_height:

            # Setting the window to the appropriate offset
            if debug:
                log.info(f"CM:: Scrolling to {scroll_x}x{offset}")
            self.webdriver.execute_script("window.scrollTo({0}, {1})".format(scroll_x, offset))
            time.sleep(screenshot_delay)

            # Get current location
            page_y_offset = self.webdriver.execute_script("return window.pageYOffset;")
            if debug:
                log.info(f"CM:: PageYOffset {page_y_offset}")

            # If the Page-y-offset hasn't moved then we actually reached
            # the end of the page, so we should be able to stop
            if orig_page_y_offset == page_y_offset:
                log.info("CM:: PageYOffset hasn't moved, forcing end")
                break
            else:
                log.info("CM:: PageYOffset has moved, allowing to continue")
                orig_page_y_offset = page_y_offset

            # Calculate new scroll height and compare with last scroll height
            new_height = self.__get_actual_height()
            if debug:
                log.info(f"CM:: New ScrollHeight Found {new_height}")

            # override the max_height if new scroll height is greater than old  scroll height
            if max_height < new_height < maximum_length_image:
                max_height = new_height
                if debug:
                    log.info(f"CM:: Using New ScrollHeight {max_height}")

            # Get the new window height so that we can set the window size
            win_height = self.webdriver.get_window_size().get('height')
            # always need to set the max_width to customize dimension else image will be cut off
            self.webdriver.set_window_size(max_width, win_height)
            if debug:
                log.info(f"CM:: Set New Window Size {max_width}x{win_height}")

            offset += view_port_height
            log.info(f"CM:: New Height Offset is {offset}")

        # Scroll the page to the top
        self.webdriver.execute_script(f"window.scrollTo(0, 0)")
        is_success = self.browser_click_buttons(screenshot_delay)
        if not is_success:
            raise Exception("Couldn't simulate clicking of buttons in browser.")
        png_ss = self.get_screenshot_by_automation(screenshot_delay)
        if png_ss:
            log.info("Screenshot taken successfully using automation.")
        else:
            log.error("Couldn't get screenshot using automation.")
        return png_ss

    def browser_click_buttons(self, screenshot_delay):
        """
            To automate the clicking of buttons in the browser for taking screenshot

            Args:
                screenshot_delay (int): Time of screenshot delay
        """
        # Adding time.sleep so that it gets time to execute the commands
        retry = 1
        success = False
        time.sleep(1)
        self.get_screenshot_xdotool()
        time.sleep(screenshot_delay)
        # Simulating the button click for downloading the screenshot directly from the browser
        # This iframe is what is being displayed after key press of Ctrl+Shift+s
        while retry < 6:
            try:
                self.webdriver.switch_to.frame("firefox-screenshots-preselection-iframe")
                success = True
                break
            except:
                log.info(f'Retrying to switch the iframe # {retry} times')
                retry += 1
                log.info(f'Sleep 1 second before retry')
                time.sleep(1)
                continue
        # There is a button called 'Save full page' which is what we click
        self.webdriver.find_element_by_class_name("full-page").click()
        # Need to switch back to default content from previous iframe
        self.webdriver.switch_to.default_content()
        time.sleep(screenshot_delay)
        # A window pops up which we want to select as the current iframe
        self.webdriver.switch_to.frame("firefox-screenshots-preview-iframe")
        time.sleep(1)
        # In the window opened, we need to click the download button
        self.webdriver.find_element_by_class_name("highlight-button-download").click()
        time.sleep(1)
        # Switch back to default content
        self.webdriver.switch_to.default_content()
        time.sleep(1)

        if success:
            return True

    def get_screenshot_xdotool(self):
        """
            To zoom out if necessary and press keys as mentioned
        """

        # Define the xdotool command
        screenshot_command = "xdotool key --delay 100 ctrl+shift+s"
        zoom_out_command = "xdotool key --delay 100 ctrl+minus"

        # Run the xdotool command in a subprocess
        try:
            # Simulate zooming out two times
            try:
                zoom_out_value = self.kwargs.get('browser_ss_preference', {}).get('BrowserAutomation', {}).get(
                    'zoom_out', None)
            except Exception as e:
                zoom_out_value = None
                log.error(f"Couldn't get the zoom out value. Error {e}")

            if zoom_out_value and zoom_out_value[0] is not None:
                for _ in range(int(zoom_out_value[0])):
                    subprocess.run(zoom_out_command, shell=True, check=True)
                    log.info("Zoomed out.")
            time.sleep(3)
            # Run the xdotool command to take a screenshot
            subprocess.run(screenshot_command, shell=True, check=True)
            log.info("Pressed the Ctrl+Shift+s Key")
        except subprocess.CalledProcessError as e:
            log.error(f"Error while running subprocess command. Error: {e}")

    def get_screenshot_by_automation(self, screenshot_delay=10):
        """
            This method reads the screenshot stored in the temporary directory
            and returns it and finally removes the directory
        Returns:
            png_ss (bytes): Image bytes if present else None
            screenshot_delay (int): Number of seconds of screenshot delay
        """
        image_dir_path = self.kwargs.get('tmp_ss_dir')
        time.sleep(screenshot_delay)
        retry = 1
        # WA-8092: Retry upto 5 times before throwing an error for getting screenshot
        while retry < 6:
            files = os.listdir(image_dir_path)
            # Check if there is exactly one file in the folder
            if len(files) == 1:
                # Get the file name
                file_name = files[0]

                # Construct the full path to the file
                image_path = os.path.join(image_dir_path, file_name)
                log.info(f'Constructed image path {image_path}')
                break
            else:
                log.info(f'Retrying getting the screenshot # {retry} times')
                retry += 1
                log.info(f'Sleep 1 second before retry')
                time.sleep(1)
                continue

        try:
            # Read the image from the mentioned path and return the image bytes
            with open(image_path, 'rb') as image_file:
                png_ss = image_file.read()
            return png_ss
        except FileNotFoundError:
            log.error(f"Error: Image file not found at '{image_path}'")
        except Exception as e:
            log.error(f"Error while reading image file: {e}")
        finally:
            try:
                shutil.rmtree(image_dir_path)
                log.info(f"Directory '{image_dir_path}' and its contents have been successfully removed.")
            except Exception as e:
                log.error(f"Error while removing the directory: {e}")

    def get_url(self, url=None):
        """
        Uses webdriver object to navigate to given URL in browser

        :param url:
            - Should be absolute URL

        :return:
            - None on success
            - HTTP Status otherwise
        """
        if not url:
            raise TypeError('No URL given for webdriver to navigate to')

        if self.webdriver is None:
            raise TypeError('No webdriver found.')

        try:
            result = self.webdriver.get(url)
        except Exception as e:
            log.error(f"Failure in attempting to retrieve URL: {url}, Error msg: {str(e)}")
            raise

        return result

    def close(self, clean=True):
        """
        Uses Webdriver's own 'close()' method to close the browser instance, the driver will still be
        in a 'Running' state and must be terminated by Webdriver.quit(). Browser's profile is also
        removed from disk unless the 'clean' flag is set to False

        :param clean:
            - Default is True, which will remove the profile directory. False will leave the artifacts
            behind. False should be set for debugging/testing only
        """
        try:
            self.webdriver.close()
        except Exception as e:
            log.error(e)
        if clean:
            self._browser_cleanup()

    def quit(self):
        """
        Uses Webdriver's own 'quit()' method to terminate the driver's process
        """
        try:
            self.webdriver.quit()
        except Exception as e:
            log.error(e)

    def _browser_cleanup(self):
        """
        This will remove the browser profile artifacts from disk
        """
        if not self.browser_profile_loc:
            raise TypeError("No browser_profile location was specified, cannot remove what we don't know.")

        if os.path.exists(self.browser_profile_loc):
            try:
                shutil.rmtree(self.browser_profile_loc)
            except Exception as e:
                log.error(e)
        else:
            raise TypeError("The profile directory specified no longer exists, nothing to remove")

    def get_page_links(self):
        """
        Gets 'a href' links via browser's javascript console

        Returns:
            list(str): list of discovered links

        """
        js_script = """
            allHrefs = []
            links = document.links;
            cssFile = document.styleSheets;
            favicon = undefined;
            faviconShort = document.querySelectorAll("[rel='shortcut icon']");
            faviconLong = document.querySelectorAll("[rel='icon']");
            if (faviconShort.length){
                favicon = faviconShort[0].href;
            }
            if (faviconLong.length){
                favicon = faviconLong[0].href;
            }
            if (favicon && allHrefs.includes(favicon) === false){
                allHrefs.push(favicon);
            }
            for (let item of cssFile){
                url = item.href
                if (url && allHrefs.includes(url) === false){
                    allHrefs.push(url);
                }
            }
            for (let item of links) {
                url = item.href
                if (url && allHrefs.includes(url) === false){
                    allHrefs.push(url);
                }
            }
            return allHrefs;
            """
        links = []
        retry = 3
        while retry > 0:
            try:
                links = self.execute_script(js_script)
            except Exception as e:
                log.error(f'{e}. Retrying to get links')
                retry -= 1
            else:
                break

        return links

    def get_page_source(self):
        """
        Gets page source from the browser after it has been loaded using
        selenium webdriver

        Returns:
            str: Page source

        """
        retry = 3
        page_source = None

        while retry > 0:
            try:
                page_source = self.webdriver.page_source
            except Exception as e:
                log.error(f'{e}. Retrying to get page source')
                retry -= 1
                time.sleep(0.5)
            else:
                break

        return page_source

    def get_page_src_urls(self):
        """
        Gets urls found in 'src' tag of the DOM via browser's console
        Returns:
            list(str): list of discovered links
        """
        js_script = """
            srcUrls = []
            src_objs = document.querySelectorAll('[src]');
            for (let item of src_objs) {
                url = item.getAttribute('src')
                if (url && srcUrls.includes(url) === false){
                    srcUrls.push(encodeURI(url));
                }
            }
            return srcUrls;
            """
        src_urls = []
        retry = 3
        while retry > 0:
            try:
                src_urls = self.execute_script(js_script)
            except Exception as e:
                log.error(f'{e}. Retrying to get links')
                retry -= 1
            else:
                break
        return src_urls

    def _load_har_export_plugin(self, wd, **kwargs):
        """
        Install har export plugin from the plugin path if `dev_tools` kwargs has been set.

        Args:
             wd (webdriver.FireFox): Webdriver object
             kwargs: Check for the `dev_tools` args has been set or not

        Returns:
            webdriver object with or without addons installed
        """
        if 'dev_tools' in kwargs and kwargs['dev_tools']:
            wd.install_addon(self.har_export_plugin_path)

        return wd

    def get_har(self, **kwargs):
        """
        Returns the har content for the captured web page

        Args:
            kwargs: check dev_tools keyword args has been set or not

        Returns:
            Dictionary containing the har content
        """
        if not self.webdriver:
            raise TypeError("No webdriver object found")

        if "dev_tools" not in self.kwargs or not self.kwargs["dev_tools"]:
            raise TypeError("Dev tools should be enabled")

        har_data = self.webdriver.execute_async_script(
            "HAR.triggerExport().then(arguments[0]);"
        )

        return har_data

    def capture_remaining_section(self, ss_chunks, total_height, win_width, win_height, scroll_x, screenshot_delay,
                                  debug=False):
        """
            This function scrolls the page to the last possible offset value and takes screenshots of the remaining
            page height
                :param ss_chunks : (list)
                        - Is maximum length where scroll and cut loop breaks.
                :param total_height : (int)
                       - document.body.scrollHeight .
                :param win_width : (int)
                       - width specified by user for the screens hot.
                :param win_height : (int)
                        - delay used between scroll calls to allow for refreshing of the page
                :param scroll_x : (bool)
                       - set to true for debug output
                :param screenshot_delay : (int)
                        - delay used between scroll calls to allow for refreshing of the page
                :param debug : (bool)
                       - set to true for debug output
                :return:
                    - png data, which should come back as binary
        """
        try:
            # calculate the remaining page height
            remaining_page_height = total_height % win_height
            if debug:
                log.info(f"CRS:: Remaining page height: {remaining_page_height}")

            # remaining page height 0 mean there is no remaining section left
            if remaining_page_height == 0:
                return None

            if debug:
                log.info(f"CRS:: Taking final screen shot")

            # modifying the height to ensure that the max page height to get accurate scroll position.
            self.webdriver.execute_script(
                "return document.body.style.height = {0}+'px'".format(total_height + win_height))
            if debug:
                log.info(f"CRS:: New document height {total_height + win_height}")

            # calculate latest offset position of remaining section
            scroll_offset = ss_chunks[0].height * len(ss_chunks)
            if debug:
                log.info(f"CRP:: Last offset position {scroll_offset}")

            # new height to resize window to get last remaining height of page with more accuracy
            new_win_height = remaining_page_height + self.webdriver.execute_script(
                "return window.outerHeight - window.innerHeight")
            # resizing the window size for remaining section

            # adding extra height of 3500px in window to include all content, some time the viewport doesn't show all
            # remaining page content
            self.webdriver.set_window_size(win_width, new_win_height + 3500)
            if debug:
                log.info(f"Telling driver to set window size: {win_width} X {new_win_height}")
            time.sleep(screenshot_delay)

            # scrolling page to the bottom offset to the remaining section
            self.webdriver.execute_script("window.scrollTo({0}, {1})".format(scroll_x, scroll_offset))
            if debug:
                log.info(f"Scrolling page to {scroll_x}x{scroll_offset}")
            time.sleep(screenshot_delay)

            image = Image.open(io.BytesIO(self.webdriver.get_screenshot_as_png()))

            return image
        except Exception as e:
            log.info(f"Couldn't capture the remaining page height {e}")
            raise e

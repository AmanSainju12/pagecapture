import io
import json
import time
from selenium import webdriver
from methods import get_screenshot_using_cut_and_merger, get_page_height, get_window_height, get_max_height
from selenium.webdriver.support.ui import WebDriverWait
from concurrent.futures import ThreadPoolExecutor


def get_screenshot(wd, full=False, df_wd=1366, df_ht=900, default_height=15000, debug=False, screenshot_delay=20):
    png_ss = None

    # Changing the input names to make more semantic sense for now
    user_wd = df_wd
    user_ht = df_ht
    cut_merge_threshold = default_height

    try:
        # Always respect the horizontal dimension from the user input or defaults.
        max_width = user_wd

        if full:
            if debug:
                print('GS:: Taking full Screen shot')
            max_height = get_max_height(wd, max_width)
            if max_height <= cut_merge_threshold:
                if debug:
                    print(f"GS:: Using Single Screenshot Capture for height {max_height}")

                # Wait so that the videos will load. Adding wait more than 2 sec will most likely result in
                # Broken pipe with empty screenshot or Remote end closed connection without response.
                # set the height, min-height and overflow to auto and visible respectively to get all visible area
                # wd.execute_script("""
                #     var style = document.createElement('style');
                #     style.innerHTML = 'html, body, div, section, header, footer, main { min-height: auto !important;
                #     height: auto !important; overflow: visible !important; }';
                #     document.head.appendChild(style);
                # """)

                new_window_height = get_window_height(wd, max_height)
                print(f"new window height: {new_window_height}")

                wd.set_window_size(max_width, new_window_height)
                print(f"setting window size: {max_width}x{new_window_height}")
                time.sleep(screenshot_delay)

                # Some web pages are not being loaded without the initial scroll, so we are scrolling to the bottom
                # of the page and scrolling back to the top to take the screenshot.
                # Reference : https://smarsh.atlassian.net/browse/WA-4020
                wd.execute_script("window.scrollTo({0}, {1})".format(max_width, max_height))
                time.sleep(screenshot_delay)

                wd.execute_script("window.scrollTo(0, 0)")
                time.sleep(screenshot_delay)

                png_ss = wd.get_screenshot_as_png()
            else:
                if debug:
                    print(f"GS:: Using Cut & Merge as Max Height {max_height} "
                          f"exceeds the threshold {cut_merge_threshold}")

                png_ss = get_screenshot_using_cut_and_merger(wd, user_wd, screenshot_delay, debug=True)
        else:
            if debug:
                print('GS:: Taking customized height screen shot as given by the user')

            # respect the height given by the user
            max_height = user_ht
            wd.set_window_size(max_width, max_height)
            time.sleep(screenshot_delay)

            png_ss = wd.get_screenshot_as_png()

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error capturing screenshot: {e}")
        return png_ss

    return png_ss


result = [{
    "name": "sdfdsf",
    "value": "sdfsdfdsfsdf",
    "page_height": "sdfsdf"
}]


def process_screenshot(_url):
    try:
        geckodriver_path = "C:/Users/aman.sainju/Desktop/Aman/geckodriver-v0.33.0-win64/geckodriver.exe"
        # service = Service(executable_path=geckodriver_path)
        options = webdriver.FirefoxOptions()
        options.add_argument("-headless")
        wd = webdriver.Firefox(executable_path=geckodriver_path, options=options)
        page_url = _url["value"]
        # Navigate to a dummy url on the same domain.
        wd.get(page_url)

        with open('cookie.json', 'r') as _file:
            cookies = json.load(_file)

        for cookie in cookies:
            wd.add_cookie(cookie)

        wd.refresh()

        # Wait for the document to be in a complete ready state
        wait = WebDriverWait(wd, 20)

        # wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

        # Wait for changes in the document's ready state (you may need to adjust the condition)
        wait.until(lambda driver: wd.execute_script("return document.readyState") == "complete")
        time.sleep(20)

        max_height = get_max_height(wd, 1336)
        if 15000 < max_height < 22000:
            result.append({"name": _url["name"], "value": page_url, "page_height": max_height})
            with open("limit_height_urls.json", "w") as fp:
                json.dump(result, fp)

            # ss = get_screenshot(wd, full=True, debug=True)
        #
        # with open("ss/final_sst_{0}.png".format(_url["name"]), "wb") as fp:
        #     fp.write(ss)

        wd.quit()
    except Exception as e:
        print(f"error while processing: {e}")
        raise e


if __name__ == '__main__':
    with open("new_franklin_urls.json", "r") as file:
        urls = json.load(file)
    # page_domain = 'https://www.franklintempleton.com'
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for _url in urls:
            futures.append(executor.submit(process_screenshot, _url))

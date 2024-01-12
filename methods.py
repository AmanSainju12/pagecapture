import io
import math
import time
from PIL import Image


def get_max_height(wd, max_width=1367):
    max_height = 0

    while True:
        previous_max_height = get_page_height(wd)
        print(f"previous_max_height {previous_max_height}")
        wd.set_window_size(max_width, previous_max_height)
        wd.execute_script("window.scrollTo(0, {0})".format(previous_max_height))
        time.sleep(20)
        new_max_height = get_page_height(wd)
        print(f"new_max_height {new_max_height}")
        print(f"prev_max_height: {previous_max_height}, new_max_height: {new_max_height}")
        if previous_max_height == new_max_height:
            max_height = new_max_height
            break
    return max_height


def get_window_height(wd, viewport):
    return viewport + wd.execute_script("return window.outerHeight - window.innerHeight")


def get_page_height(wd):
    scroll_height = int(wd.execute_script('return document.body.scrollHeight'))
    client_height = int(wd.execute_script('return document.body.clientHeight'))
    offset_height = int(wd.execute_script('return document.body.offsetHeight'))
    document_offset_height = int(wd.execute_script('return document.documentElement.offsetHeight'))
    document_client_height = int(wd.execute_script('return document.documentElement.clientHeight'))
    document_scroll_height = int(wd.execute_script('return document.documentElement.scrollHeight'))

    # find max height of the current page
    max_height = max([scroll_height, client_height, offset_height, document_scroll_height, document_client_height,
                      document_offset_height])
    print(f"found max height: {max_height}")

    return max_height


def get_combined_screenshot(slices, width):
    total_height = 0

    try:
        # calculating total image height
        for image in slices:
            total_height += image.height

        # adding more extra 150px image screenshot height
        screenshot = Image.new(slices[0].mode, (width[0], total_height + 150))

        offset = 0

        for img in slices:
            screenshot.paste(img, (0, offset))
            offset += img.height

        screenshot_data = io.BytesIO()
        screenshot.save(screenshot_data, format='PNG')
        screenshot_data.seek(0)

        return screenshot_data.read()
    except Exception as e:
        raise e


def capture_remaining_page(wd, ss_chunks, total_height, win_width, viewport, scroll_x, screenshot_delay):
    try:
        # calculate the remaining page height
        remaining_page_height = total_height % viewport
        print(f"remaining height: {remaining_page_height}")

        # remaining page height 0 mean there is no remaining section left
        if remaining_page_height == 0:
            return None

        print(f"CRP:: Taking final screenshot")

        # modifying the height to ensure that the max page height is constant.
        wd.execute_script("return document.body.style.height = {0}+'px'".format(total_height))

        # gives latest offset data
        scroll_offset = ss_chunks[0].height * len(ss_chunks)

        # new height to resize window to get last remaining page with more accuracy
        new_win_height = get_window_height(wd, remaining_page_height)

        # resizing the window size for remaining section
        wd.set_window_size(win_width, new_win_height)
        print(f"setting new viewport size: {win_width} X {new_win_height}")

        time.sleep(screenshot_delay)

        # scrolling page to the bottom offset to the remaining section
        wd.execute_script("window.scrollTo({0}, {1})".format(scroll_x, scroll_offset))

        time.sleep(screenshot_delay)

        image = Image.open(io.BytesIO(wd.get_screenshot_as_png()))

        return image
    except Exception as e:
        print(f"error-capture-remaining-page {e}")
        raise e


def get_screenshot_using_cut_and_merger(wd, win_width, screenshot_delay, debug=False, win_height=15000):
    ss_chunks = []
    offset = 0
    scroll_x = 0
    window_width = win_width

    # returns max page height after scrolling the page up to the bottom
    max_height = get_max_height(wd, window_width)
    print(f"found new page height: {max_height}")

    wd.set_window_size(win_width, max_height)
    print(f"window size {win_width}x{wd.execute_script("return window.outerHeight")}")
    time.sleep(screenshot_delay)

    viewport = wd.execute_script("return window.innerHeight")
    print(f"viewport height {viewport}")

    max_ss_count = math.floor(max_height / viewport)
    print(f"CM:: total possible screenshot excluding last remaining screenshot: {max_ss_count}")

    # initializing ss count
    total_ss_count = 0
    print(f"CM:: total_ss_taken : {total_ss_count}")

    while total_ss_count < max_ss_count:
        # Setting the window to the appropriate offset
        if debug:
            print(f"CM:: Scrolling to {scroll_x}x{offset}")
        wd.execute_script("window.scrollTo({0}, {1})".format(scroll_x, offset))
        time.sleep(screenshot_delay)

        img = Image.open(io.BytesIO(wd.get_screenshot_as_png()))

        # always get the offset from the image height to get the next position with accuracy
        offset += img.height
        if debug:
            print(f"CM:: New Height Offset is {offset}")

        ss_chunks.append(img)

        total_ss_count += 1

    # check and capture last screenshot if available
    last_image = capture_remaining_page(wd, ss_chunks, max_height, window_width, viewport, scroll_x,
                                        screenshot_delay)

    if last_image:
        ss_chunks.append(last_image)

    width = [int(window_width)]
    png_ss = get_combined_screenshot(ss_chunks, width)

    return png_ss

# def check_scrollbar(wd):
#     is_scrollable = False
#     client_height = wd.execute_script("return document.documentElement.clientHeight")
#     scroll_height = wd.execute_script("return document.documentElement.scrollHeight")
#     if client_height < scroll_height:
#         is_scrollable = True
#     return is_scrollable

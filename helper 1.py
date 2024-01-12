import io
import sys
from PIL import Image
from wa.core.logging.logger import StandardOutLoggingHandler

"""
This helper utility class will be used for screen shot transformations ( converting from png to JPG ) and also 
does screen shot validations.
"""

log = StandardOutLoggingHandler("wa.browser_handler").get_logger()
class ScreenshotHelper:
    @staticmethod
    def convert_png_jpeg(png_raw_data):
        """
           This method  converts the screenshot bytes in png format to bytes in jpeg format
            and also does screenshot validation.
           Basically this could be used to convert snapshot from png to JPEG format.

          :param png_raw_data
                  - bytes of the png in png format
                  - Accepted Values: class 'bytes',
           Returns:
               The return screenshot value in 'bytes'  with the jpeg format.

           Raises:
               Exception: If param  'png_raw_data' validation fails  if screens hot is invalid.
           """

        if ScreenshotHelper.is_valid_screenshot(png_raw_data, 1000):
            stream = io.BytesIO(png_raw_data)
            image = Image.open(stream)
            rgb_im = image.convert('RGB')
            screenshot_data = io.BytesIO()
            rgb_im.save(screenshot_data, format="JPEG")
            screenshot_data.flush()
            screenshot_data.seek(0)
            return screenshot_data.read()
        else:
            raise Exception(
                'Invalid  screen shot  to convert  as size could be  either less than 1KB or might be empty')

    @staticmethod
    def is_valid_screenshot(p_object, size):
        """
          This function validates the screenshot by checking if the size is greater than expected
           size and is not empty.
             :param : Object
              Return true if the screenshot is valid and false otherwise
           """

        # Checks if the size is greater than expected size and is not empty
        if p_object and sys.getsizeof(p_object) > size:
            return True
        else:
            return False

    @staticmethod
    def get_combined_screenshot(slices, width):
        """
            This function merges the captured screenshot chunks in memory and returns the merged
            screenshot as bytes IO.
               :param : slices (chunks of screenshots), offset(total height) ,width
                Return screenshot bytes io
           """

        total_image_height = 0

        # calculating total height of image
        for img in slices:
            total_image_height += img.size[1]

        # setting the screenshot image height and adding extra 150 to ensure image doesn't crop
        screenshot = Image.new(slices[0].mode, (width[0], total_image_height + 150))

        offset = 0
        for img in slices:
            screenshot.paste(img, (0, offset))
            offset += img.size[1]

        screenshot_data = io.BytesIO()
        screenshot.save(screenshot_data, format='PNG')
        screenshot_data.seek(0)
        return screenshot_data.read()

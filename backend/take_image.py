from datetime import datetime
from lucidcamera import LucidCamera
import cv2

ip_address_1 = '192.168.3.7'
# ip_address_2 = '192.168.3.4'
target_brightness = 128
filename1 = 'cup.png'
# filename2 = 'cassette.png'

if __name__ == '__main__':
    
    cam1 = LucidCamera(ip_address_1, target_brightness)
    # cam2 = LucidCamera(ip_address_2, target_brightness)


    cam1.get_image(filename1)
    img = cv2.imread('cup.png')
    cv2.imshow("Window", img)
    cv2.waitKey(5000)
    cv2.destroyAllWindows()
    # cam2.get_image(filename2)
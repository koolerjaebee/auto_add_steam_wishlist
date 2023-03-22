import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

wishlist_user_id = input("Input user ID that you want to copy\n")

flag = 0
i = 0
while not flag:
    print(f"Downloading 'wishlist{i}.json'...")
    response = requests.get(f"https://store.steampowered.com/wishlist/id/{wishlist_user_id}/wishlistdata/?p={i}")
    json_file = response.json()
    if not json_file:
        flag = 1
    else:
        with open(f"wishlist{i}.json", "w") as f:
            json.dump(json_file, f)
        i += 1


wishlist = {}

for idx in range(i+1):
    
    with open(f"wishlist{idx}.json", "r") as rawdata:
        wishlist.update(json.load(rawdata))
    
# 찜목록에 추가하고 싶은 게임의 app_id 리스트
app_ids = []

for item in wishlist:
    app_ids.append(item)

user_id = input("Input your ID\n")
print(f"You entered \n<  {user_id}  >")
user_password = input("Input your password\n")
print(f"You entered \n<  {user_password}  >")

driver=webdriver.Chrome()

driver.get("https://store.steampowered.com/login/")
driver.implicitly_wait(5)

driver.find_element(By.XPATH, "//*[@id='responsive_page_template_content']/div/div[1]/div/div/div/div[2]/div/form/div[1]/input").send_keys(user_id)
driver.find_element(By.XPATH, "//*[@id='responsive_page_template_content']/div/div[1]/div/div/div/div[2]/div/form/div[2]/input").send_keys(user_password)
driver.find_element(By.XPATH, "//*[@id='responsive_page_template_content']/div/div[1]/div/div/div/div[2]/div/form/div[4]/button").click()


input("Press any button to start...\n")

print("Start!")


for app_id in app_ids:    
    driver.get(f"https://store.steampowered.com/app/{app_id}")
    driver.implicitly_wait(5)
    # 생년월일 입력 원하는 경우를 위해 if구문 추가
    
    try:
        element = driver.find_element(By.XPATH, "//*[@id='app_agegate']/div[1]/div[2]/div")
    except:
        element = None
        
    if element:
        day_element = Select(driver.find_element(By.XPATH, "//*[@id='ageDay']"))
        month_element = Select(driver.find_element(By.XPATH, "//*[@id='ageMonth']"))
        year_element = Select(driver.find_element(By.XPATH, "//*[@id='ageYear']"))
        
        day_element.select_by_value("13")
        driver.implicitly_wait(5)     
        month_element.select_by_value("April")
        driver.implicitly_wait(5)     
        year_element.select_by_value("1993")
        driver.implicitly_wait(5)     
        
        driver.find_element(By.XPATH, "//*[@id='view_product_page_btn']").click()
        driver.implicitly_wait(5)        
            
    # 이미 찜일시 생략 구문 추가
    wishlist_btn = driver.find_element(By.XPATH, "//*[@id='add_to_wishlist_area']")
    
    try:
        element = wishlist_btn.get_attribute("style")
    except:
        element = None
        
    if element != "display: none;":
        wishlist_btn.click()
        time.sleep(15)
    
    print(f"{app_id} done!")

print("Finish!!")

driver.close() #현재 브라우저만 닫기

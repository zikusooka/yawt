#!/usr/bin/env python
"""
This tool will scrape weather forecast data from top weather sites
like weather.com, accuweather

""" 
import requests
from bs4 import BeautifulSoup
import time
import datetime
from datetime import datetime
import subprocess
import argparse
import sys
import urllib3
from googlesearch import search
import os
from dotenv import load_dotenv
import ssl
import warnings
import unidecode
from urllib.parse import urlparse
import fileinput
from gtts import gTTS


# Copyright
__author__ = 'Joseph Zikusooka.  Jambula Labs @copyright 2024-2025 All rights reserved'

default_weather_source = 'https://weather.com/en-UG/weather'
weather_source_search_domain = urlparse(default_weather_source).netloc

share_dir = '/usr/share/jambula'
sounds_dir = f'{share_dir}/sounds'
images_dir = f'{share_dir}/images'
tmp_dir = '/tmp'

www_ip = '127.0.0.1'
www_port = '8080'

online_http_server = 'http://172.217.170.196'
local_http_server = f'{www_ip}:{www_port}'

weather_pages_dir = f'{share_dir}/weather'
weather_today_page_filename = 'weather_com_today.html'
weather_ten_day_page_filename = 'weather_com_ten_day.html'
weather_today_local_url = f'http://{www_ip}:{www_port}/{weather_today_page_filename}'    
weather_ten_day_local_url = f'http://{www_ip}:{www_port}/{weather_ten_day_page_filename}'
weather_today_page_filepath = f'{weather_pages_dir}/{weather_today_page_filename}'
weather_ten_day_page_filepath = f'{weather_pages_dir}/{weather_ten_day_page_filename}'
weather_today_page_file_freshness_threshold = 900
tts_output_file_freshness_threshold = 900
text_output_file_freshness_threshold = 900

tts_output_dir = tmp_dir + '/' + 'tts' + '/' + 'weather'   
tts_input_file = tmp_dir + '/' + 'tts_output.wav'    
tts_concat_input_file = tts_output_dir + '/' + 'input_files_weather_scraper.txt'
    
tts_output_filename = 'weather_forecast_weather_com.mp3'
text_output_filename = 'weather_forecast_weather_com.txt'
tts_output_file = tmp_dir + '/' + tts_output_filename
text_output_file = tmp_dir + '/' + text_output_filename

weather_update_tts_header_filename = f'{sounds_dir}/weather_update_for_area.mp3'

sounds_tool = '/usr/bin/mpv'
sounds_gain = '100'
sounds_options = '--no-video'
sounds_alert_speaker_prompt = f'{sounds_dir}/Airplane-ding-sound.mp3'

DateDayofWeek = datetime.now().strftime('%a')
DateToday = datetime.now().strftime('%d')
TimeNowHour = datetime.now().strftime('%-H')

project_global_settings_file = '/etc/JambulaTV/global-settings.cfg'
load_dotenv(project_global_settings_file)

mqtt_broker_ip = os.environ['MQTT_BROKER_IP']
mqtt_broker_port = os.environ['MQTT_BROKER_PORT']
mqtt_topic_weather_dot_com = 'JambulaTV/house/status/weather/weather_dot_com'
mqtt_payload_weather_dot_com = 'rain'


def usage ():
    parser = argparse.ArgumentParser(description='JambulaTV: Display, read, and save the weather forecast for a given location')
    parser.add_argument('--location', dest='location', help='[location]', type=str, required=True, default='Kampala, Uganda')
    parser.add_argument('--task', dest='task', choices=['fetch', 'display', 'read'], help='[task]', type=str, required=True)
    parser.add_argument('--offline', dest='offline', choices=['yes', 'no'] ,help='[offline]', type=str, required=False)
    return parser

def hide_python3_upgrade_warnings():
    # Add support for unverified SSL connections
    if (not os.environ.get('PYTHONHTTPSVERIFY', '') and
        getattr(ssl, '_create_unverified_context', None)): 
        ssl._create_default_https_context = ssl._create_unverified_context
        # Ignore all 'unclosed' warnings e.g. unclosed file or socket
        warnings.filterwarnings(action="ignore", 
                            message="unclosed", 
                            category=ResourceWarning)

def check_internet_connectivity(http_server):
    if OFFLINE == 'yes':
      print (f'Offline mode: Internet connectivity checks disabled')
      return
    http = urllib3.PoolManager(timeout=3.0)
    try:
        r = http.request('GET', http_server, preload_content=False)
        code = r.status
        r.release_conn()
        if code == 200:
            return True
        else:
            return False
    except:
        return False

def start_web_server ():
    site_is_reachable = check_internet_connectivity(http_server=local_http_server)
    if site_is_reachable == False:
        # Start web server to serve weather pages
        subprocess.Popen(['/usr/bin/sudo', '/usr/bin/python', '-m', 'http.server', www_port, '-d', weather_pages_dir])
        print(f'Info: The directory [{weather_pages_dir}] is now accessible at http://{www_ip}:{www_port}')
    else:
        print(f'Info: A web server is already running at: {local_http_server}')

def mqtt_publish (mqtt_topic, mqtt_payload):
    cmd = [ '/usr/bin/mosquitto_pub', '--quiet', '-h', mqtt_broker_ip, '-p', mqtt_broker_port, '-t', mqtt_topic, '-m', mqtt_payload ]
    publish = subprocess.check_call(cmd)
    return publish

def check_file_freshness(FILE, FRESHNESS_THRESHOLD_SECS):
    try:
        file_mtime = os.stat(FILE)
        file_mtime = file_mtime.st_mtime
        current_time = time.time() 
        file_age = current_time - file_mtime
        file_age = int(file_age)

        if file_age < FRESHNESS_THRESHOLD_SECS:
            return True
        else:
            return False
        return file_age
    except:
        print (f'Warning: The file {FILE} was not found')

def celsius(a_string):
    out = a_string.replace("°", "")
    cel= round((int(out) - 32) * 5.0/9.0)
    return cel

def make_soup(url):
    page = requests.get(url)
    data = page.content
    soup = BeautifulSoup(data, 'html.parser')
    return soup

def download_save_weather_page(FILE, URL):
    if os.path.exists(FILE):
        subprocess.check_call(['/usr/bin/sudo', '/usr/bin/rm', tmp_dir + '/' + FILE])
    subprocess.check_call(['/usr/bin/curl', '-kLsS', '-m', '60', '-A', 'Mozilla/5.0', '-o', tmp_dir + '/' + FILE, URL])
    subprocess.check_call(['/usr/bin/sudo', '/usr/bin/cp', tmp_dir + '/' + FILE, weather_pages_dir])

def search_and_fetch_weather_data():
    # Create weather pages directory if non existent
    if not os.path.exists(weather_pages_dir):
        subprocess.check_call(['/usr/bin/sudo', '/usr/bin/mkdir', '-p', weather_pages_dir])
    # Skip if offline mode is specified 
    if OFFLINE == 'yes':
      for outputfile in [text_output_file, tts_output_file]:
        if os.path.exists(outputfile):
          subprocess.check_call(['sudo', '/usr/bin/rm', '-f', outputfile])
      for outputfile in [weather_today_page_filepath, weather_ten_day_page_filepath]:
        if not os.path.exists(outputfile):
          print (f'Error: The weather source file {[outputfile]} does not exist!')
          sys.exit(0)
      return
    # Search for weather
    WEATHER_SEARCH_STRING = f'"{LOCATION}" "Weather" "Today" "Weather Forecast and Conditions'
    FILE = weather_today_page_filepath
    FRESHNESS_THRESHOLD_SECS = weather_today_page_file_freshness_threshold
    file_is_fresh = check_file_freshness(FILE,FRESHNESS_THRESHOLD_SECS)
    # Remove weather forecast text and audio output files if not fresh
    if (file_is_fresh == False or file_is_fresh == None):
        for outputfile in [weather_today_page_filepath, weather_ten_day_page_filepath, text_output_file, tts_output_file]:
            if os.path.exists(outputfile):
                subprocess.check_call(['sudo', '/usr/bin/rm', '-f', outputfile])
    # Check for Internet connectivity
    site_is_reachable = check_internet_connectivity(http_server=online_http_server)
    if site_is_reachable == False:
        print (f'Error: There\'s no Internet connection, therefore I can not download weather data for {LOCATION} from {weather_source_search_domain}')
        sys.exit(0)
    elif (file_is_fresh == False or file_is_fresh == None):
        print (f'Info: Downloading fresh weather information for {LOCATION}, please wait')
        for SEARCH_URL in search(WEATHER_SEARCH_STRING, tbs='d', safe='off', num=5, stop=1, extra_params={'as_sitesearch': weather_source_search_domain}):
            search_url_parts = urlparse(SEARCH_URL)
            canonicalCityId = search_url_parts.path
            canonicalCityId = canonicalCityId.rsplit('/', 1)[1]
            WEATHER_TODAY_URL = default_weather_source + '/today/l/' + canonicalCityId
            WEATHER_TENDAY_URL = default_weather_source + '/tenday/l/' + canonicalCityId
            #
            # TODAY
            try:
                download_save_weather_page(weather_today_page_filename, WEATHER_TODAY_URL)
            except:
                print (f'Warning: Download of Today weather data failed ...')
                pass
            # 10-DAY
            try:
                download_save_weather_page(weather_ten_day_page_filename, WEATHER_TENDAY_URL)
            except:
                print (f'Warning: Download of 10-day weather data failed ...')
                pass
    return weather_source_search_domain

def extract_timestamp_current():
    soup_today = make_soup(weather_today_local_url)
    weather_timestamp = soup_today.select('.CurrentConditions--header--kbXKR')
    for current_timestamp in weather_timestamp:
        weather_village = current_timestamp.select('.CurrentConditions--location--1YWj_')[0].get_text()
        weather_timestamp = current_timestamp.select('.CurrentConditions--timestamp--1ybTk')[0].get_text()
        return weather_village, weather_timestamp

def extract_precipitation_data_current():
    soup_today = make_soup(weather_today_local_url)
    weather_precipitation = soup_today.find_all(class_='InsightNotification--text--35QdL')
    current_precipitation = []
    for current_precipitation_summary in weather_precipitation:
        summary_precipitation = current_precipitation_summary.get_text().rstrip().replace('.', '', 1)
        return summary_precipitation

def extract_air_quality_data_current():
    soup_today = make_soup(weather_today_local_url)
    air_quality_status = soup_today.find_all(class_='AirQualityText--severity--W9CtX')
    #air_quality_index = soup_today.find_all(class_='AirQuality--col--3I-4C')
    current_air_quality = []
    for current_air_quality_summary in air_quality_status:
        summary_air_quality = current_air_quality_summary.get_text().rstrip().replace('.', '', 1)
        return summary_air_quality

def scrape_read_weather_today():
    soup_today = make_soup(weather_today_local_url)
    weather_current_conditions = soup_today.select('.CurrentConditions--columns--30npQ')
    for current_conditions in weather_current_conditions:
        weather_village, weather_time = extract_timestamp_current()
        weather_time = weather_time.split()[2]
        weather_time = datetime.strptime(weather_time, '%H:%M').strftime('%-I:%M %p')
        summary_current = current_conditions.select('.CurrentConditions--phraseValue--mZC_p')[0].get_text()
        temperature_current = current_conditions.select('.CurrentConditions--tempValue--MHmYY')[0].get_text()
        temperature_current = unidecode.unidecode(temperature_current)
        temperature_current = temperature_current.replace('deg','')
        temperature_forecast = current_conditions.select('.CurrentConditions--tempHiLoValue--3T1DG')[0].get_text()
        temperature_forecast = unidecode.unidecode(temperature_forecast)
        temp_high_low = temperature_forecast.replace('deg','')
        temp_high_low = temp_high_low.replace('*','').split()
        forecast_period1 = (temp_high_low)[0]
        temperature_period1 = (temp_high_low)[1]
        forecast_period2 = (temp_high_low)[2]
        temperature_period2 = (temp_high_low)[3]
        try:
            precipitation_current = extract_precipitation_data_current()
        except:
            precipitation_current = None
        weather_precipitation = f'{precipitation_current}.'
        
        summary_air_quality = extract_air_quality_data_current()
        air_quality_text = f'The air quality in your area is currently {summary_air_quality}'

        weather_header = f''
        weather_footer = f'{air_quality_text}. Source: {weather_source_search_domain} as of {weather_time}'
        weather_temperature = f'{temperature_current}'
        weather_conditions = f'{summary_current}'
        weather_temperature_period1 = f'{forecast_period1} time highs of {temperature_period1} and'
        weather_temperature_period2 = f'{forecast_period2} time lows of {temperature_period2}'
        if TimeNowHour <= '17':
            weather_temperature_period = f'{weather_temperature_period1} {weather_temperature_period2} degrees celsius '
        else:
            weather_temperature_period = f'{weather_temperature_period2} degrees celsius'
        if precipitation_current is not None:
            tts_text_message = f'{weather_precipitation} Currently {weather_conditions} and the temperature is {weather_temperature} degrees celsius.'
        else:
            tts_text_message = f'Currently {weather_conditions} and the temperature is {weather_temperature} degrees celsius.'
        return tts_text_message, weather_footer, precipitation_current

def scrape_read_weather_ten_day():
    soup_ten_day = make_soup(weather_ten_day_local_url)
    weather_ten_days = soup_ten_day.select('.DailyContent--DailyContent--1yRkH')
    tts_text_message = []
    count = 1
    for weather_forecast in weather_ten_days:
        period = weather_forecast.select('.DailyContent--daypartName--3emSU')[0].get_text(strip=True).split()
        day_of_week = period[0]
        date = period[1].replace('|', '')
        time_of_day = period[2]
        temperature_now = weather_forecast.select('.DailyContent--temp--1s3a7')[0].get_text()
        temperature_now_celsius = celsius(temperature_now)
        summary_ten_day = weather_forecast.select('.DailyContent--narrative--3Ti6_')[0].get_text()
        if count <= 2:

            if day_of_week == DateDayofWeek:
                if time_of_day == 'Day' and count == 1:
                    tts_text_message.append(f'Today: {summary_ten_day}')

                elif time_of_day == 'Night' and count == 1:
                    tts_text_message.append(f'Tonight: {summary_ten_day}')

                elif time_of_day == 'Day' and count == 2:
                    tts_text_message.append(f'Later today: {summary_ten_day}')

                elif time_of_day == 'Night' and count == 2:
                    tts_text_message.append(f'Later tonight: {summary_ten_day}')

            else:
                tts_text_message.append(f'Tomorrow: {summary_ten_day}')
        count += 1

    tts_text_message = map(str,tts_text_message)
    tts_text_message = ' '.join(tts_text_message)
    tts_text_message = unidecode.unidecode(tts_text_message)
    tts_text_message = tts_text_message.replace('oC', ' degrees celsius')
    tts_text_message = tts_text_message.replace('degC', ' degrees celsius')
    # Wind direction
    tts_text_message = tts_text_message.replace('Winds N ', 'North Winds ')
    tts_text_message = tts_text_message.replace('Winds S ', 'South Winds ')
    tts_text_message = tts_text_message.replace('Winds E ', 'East Winds ')
    tts_text_message = tts_text_message.replace('Winds W ', 'West Winds ')
    tts_text_message = tts_text_message.replace('Winds ENE ', 'East North East Winds ')
    tts_text_message = tts_text_message.replace('Winds ESE ', 'East South East Winds ')
    tts_text_message = tts_text_message.replace('Winds WNW ', 'West North West Winds ')
    tts_text_message = tts_text_message.replace('Winds WSW ', 'West South West Winds ')
    for wind_direction in [ 'Winds NNE ', 'Winds NE ' ]:
        tts_text_message = tts_text_message.replace(wind_direction, "North East Winds ")
    for wind_direction in [ 'Winds NNW ', 'Winds NW ' ]:
        tts_text_message = tts_text_message.replace(wind_direction, "North West Winds ")
    for wind_direction in [ 'Winds SSE ', 'Winds SE ' ]:
        tts_text_message = tts_text_message.replace(wind_direction, "South East Winds ")
    for wind_direction in [ 'Winds SSW ', 'Winds SW ' ]:
        tts_text_message = tts_text_message.replace(wind_direction, "South West Winds ")
    tts_text_message = tts_text_message.replace('km/h', 'kilometers per hour')
    return tts_text_message

def save_weather_forecast_summary():
    for outputfile in [text_output_file, tts_output_file]:
        if os.path.exists(outputfile):
            subprocess.check_call(['/usr/bin/sudo', '/usr/bin/rm', outputfile])
    tts_text_today, weather_footer, precipitation_current = scrape_read_weather_today()
    tts_text_ten_day = scrape_read_weather_ten_day()
    print(f'Saving weather forecast summary for {LOCATION} ...')
    f = open(text_output_file, 'a')
    for forecast in [tts_text_today, tts_text_ten_day, weather_footer]:
      f.write(f'{forecast} ')
    f.close()

    if os.path.exists(text_output_file) and os.stat(text_output_file).st_size != 0 and TASK != 'display':
        for line in fileinput.input(files = text_output_file):
            weather_summary_text = line
            # Notify desktop user of weather update
            if os.path.exists('/usr/bin/notify-send'):
                subprocess.Popen(['/usr/bin/notify-send', '-t', '3000', '-a', 'Weather Update', '-i', f'{images_dir}/weather-showers-day.png', 'Weather Update: ', weather_summary_text])
            # Convert weather text to speech
            try:
                print(f'Converting weather forecast summary from text to speech')
                googleTTS = gTTS(text=weather_summary_text, lang='en', slow=False)
                googleTTS.save(tts_output_file)
            except:
                print(f'Error: Failed to convert weather forecast summary from text into speech')

        # Move text output file to weather pages directory
        subprocess.check_call(['/usr/bin/sudo', '/usr/bin/cp', '-v', text_output_file, weather_pages_dir])

    if os.path.exists(tts_output_file) and os.stat(tts_output_file).st_size == 0:
        subprocess.check_call(['/usr/bin/sudo', '/usr/bin/rm', tts_output_file])
    else:
        # Move tts output file to weather pages directory
        subprocess.check_call(['/usr/bin/sudo', '/usr/bin/cp', '-v', tts_output_file, weather_pages_dir])

def display_weather_forecast():
    FILE = text_output_file
    FRESHNESS_THRESHOLD_SECS = text_output_file_freshness_threshold
    file_is_fresh = check_file_freshness(FILE,FRESHNESS_THRESHOLD_SECS)
    if not os.path.exists(text_output_file) or os.stat(text_output_file).st_size == 0 or (file_is_fresh == False):
        search_and_fetch_weather_data()
        save_weather_forecast_summary()
    for line in fileinput.input(files = text_output_file):
        weather_summary_text = line
        print(f'Displaying weather forecast for {LOCATION} ...')
        print (f'{weather_summary_text}')

def read_weather_forecast():
    FILE = tts_output_file
    FRESHNESS_THRESHOLD_SECS = tts_output_file_freshness_threshold
    file_is_fresh = check_file_freshness(FILE,FRESHNESS_THRESHOLD_SECS)
    if not os.path.exists(FILE) or os.stat(FILE).st_size <= 0 or file_is_fresh == False:
        search_and_fetch_weather_data()
        save_weather_forecast_summary()
    if os.path.exists(FILE) and os.stat(FILE).st_size >= 50:
        sounds_alert = FILE
        weather_update_alert = weather_update_tts_header_filename
        print(f'Reading weather forecast for {LOCATION} ...')
        subprocess.check_call([sounds_tool, sounds_options, f'--volume={sounds_gain}', sounds_alert_speaker_prompt])
        subprocess.check_call([sounds_tool, sounds_options, f'--volume={sounds_gain}', weather_update_alert])
        subprocess.check_call([sounds_tool, sounds_options, f'--volume={sounds_gain}', sounds_alert])
    else:
        print(f'Error: The file {FILE} is does not exist')


if __name__ == "__main__":

    hide_python3_upgrade_warnings()
    
    parser = usage ()
    args = parser.parse_args()
    LOCATION = args.location
    TASK = args.task
    OFFLINE = args.offline

    start_web_server ()

    if TASK == 'fetch':
        search_and_fetch_weather_data()
        save_weather_forecast_summary()
        #if precipitation_current is not None:
            #weather_dot_com_alert_via_mqtt = mqtt_publish(mqtt_topic_weather_dot_com, mqtt_payload_weather_dot_com)

    elif TASK == 'display':
        display_weather_forecast()

    elif TASK == 'read':
        read_weather_forecast()

# encoding: utf-8

from handlers.base import *
import logging
import datetime
import re
import avtoru_parser
from google.appengine.api import taskqueue

class AvtoruCron(AppHandler):
    def get(self):
        categories = [15, 31, 32, 33, 34, 16, 1]

        for cat in categories:
            url = "http://all.auto.ru/list/?category_id="+str(cat)+"&section_id=1&subscribe_id=&filter_id=&mark_id=0&year%5B1%5D=&year%5B2%5D=&color_id=&price_usd%5B1%5D=&price_usd%5B2%5D=&currency_key=RUR&body_key=&run%5B1%5D=&run%5B2%5D=&engine_key=0&engine_volume%5B1%5D=&engine_volume%5B2%5D=&drive_key=&engine_power%5B1%5D=&engine_power%5B2%5D=&transmission_key=0&used_key=&wheel_key=&custom_key=&available_key=&change_key=&owner_pts=&stime=2&country_id=1&has_photo=0&region%5B%5D=89&region%5B%5D=32&region_id=89&sort_by=2&output_format=1&client_id=0&extras%5B1%5D=0&extras%5B2%5D=0&extras%5B3%5D=0&extras%5B4%5D=0&extras%5B5%5D=0&extras%5B6%5D=0&extras%5B7%5D=&extras%5B8%5D=0&extras%5B9%5D=0&extras%5B10%5D=0&extras%5B11%5D=0&extras%5B12%5D=&extras%5B13%5D=0&extras%5B14%5D=0&extras%5B15%5D=0&extras%5B16%5D=0&extras%5B17%5D=0&extras%5B18%5D=&extras%5B19%5D=&extras%5B20%5D=&extras%5B21%5D=&extras%5B22%5D=&extras%5B23%5D=0&extras%5B24%5D=0&extras%5B25%5D=&extras%5B26%5D=&extras%5B27%5D=0&extras%5B28%5D=0&extras%5B29%5D=&submit=%D0%9D%D0%B0%D0%B9%D1%82%D0%B8"

            taskqueue.add(queue_name = 'avtoru', url="/avto/ads", params = {'base_url': url})

route("/cron/avto/ads", AvtoruCron)


class AvtoruTask(AppHandler):
    def get(self):
        try:
            page = int(self.request.get('page'))
        except:
            page = 1

        settings = avtoru_parser.AvtoSettings().all().get()

        if settings is None:
            settings = avtoru_parser.AvtoSettings()
            settings.put()

        base_url = self.request.get('base_url')       

        links = avtoru_parser.AvtoruParser(base_url, page).get_list()

        for link in links:
            taskqueue.add(queue_name = 'avtoru', url="/avto/ad", params = {'url': link})

        if len(links) > 40:
            taskqueue.add(queue_name = 'avtoru', url="/avto/ads", params = {'page': page+1, 'base_url': base_url})

    def post(self):
        self.get()

route("/avto/ads", AvtoruTask)


import time
import logging
from datetime import timedelta

class ProcessAd(AppHandler):
    def post(self):
        url = self.request.get('url')

        logging.info("Processing ad: %s" % url)

        parser = avtoru_parser.AvtoruAdParser(url).parse()

        if avtoru_parser.AvtoAd.get_by_key_name(url) is None:
            start_from = date.today() - timedelta(days = 30)

            if avtoru_parser.AvtoAd().all().filter("phone =", parser.phone).filter("created_at >", start_from).get() is None:
                logging.info("Processing avto ad: %s, %s" % (url, parser.phone))
                logging.info(parser.date)

                ad = avtoru_parser.AvtoAd(key_name = "%s_%d" % (url, time.time()),
                                          phone = parser.phone,
                                          created_at = parser.date)

                ad.put()
            else:
                logging.info("Phone found: %s" % parser.phone)
        else:
            logging.info("Ad found: %s" % url)

route("/avto/ad", ProcessAd)


from datetime import date
from datetime import datetime

def query_counter(q, cursor=None, limit=1000):
    if cursor:
        q.with_cursor(cursor)
    count = q.count(limit=limit)
    if count == limit:
        return count + query_counter(q, q.cursor(), limit=limit)
    return count

class AvtoList(AppHandler):
    def get(self):
        today_date = (datetime.now()+timedelta(hours=4)).date()

        today = query_counter(avtoru_parser.AvtoAd.all().order('-created_at').filter('created_at =', today_date))

        yesterday = query_counter(avtoru_parser.AvtoAd.all().order('-created_at').filter('created_at =', today_date-timedelta(1)))


        self.render_template("avto_ads.html", {'today':today, 'yesterday':yesterday })

route("/", AvtoList)


from dateutil import parser
import re

class AvtoDownload(AppHandler):
    def get(self):
        if self.request.get('date') == 'today':
            _date = date.today()
        elif self.request.get('date') == 'yesterday':
            _date = date.today()-timedelta(1);
        else:
            _date = parser.parse(self.request.get('date'))

        ads = avtoru_parser.AvtoAd.all().order('-created_at').filter('created_at =', _date).fetch(5000)

        if self.request.get('show_url') == '1':
            phones = [ad.phone+" "+re.sub(r"_\d*$",'',ad.key().name()) for ad in ads]
        else:
            phones = [ad.phone for ad in ads]
            

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write("\n".join(phones))

route("/avto/download", AvtoDownload)


class AvtoSettings(AppHandler):
    def post(self):
        settings = avtoru_parser.AvtoSettings().all().get()

        settings.price_start = int(self.request.get('price_start'))
        settings.price_end = int(self.request.get('price_end'))

        settings.put()

route("/avto/settings", AvtoSettings)

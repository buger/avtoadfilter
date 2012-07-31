# encoding: utf-8
from bs4 import BeautifulSoup
import re
import urllib2
import hashlib
from dateutil import parser
from dateutil.relativedelta import relativedelta
import logging
from simplejson import loads,dumps
import cookielib
import md5
import datetime

from spb_metro import *
from msk_metro import *

rPHONE = re.compile("(?:\d[ \-\)\(\dx\.]{0,2}(?!\n)){6,12}")
rMOBILE_PHONE = re.compile("9(?:\d[ \-\)\(\dx\.]{0,2}){6,10}")
rREPLACE = re.compile("\D")
rPHONE_PREFIX = re.compile("^[87]")
rCITY_PREFIX = re.compile("^(812|813|811|495|499)")
rAGENT = re.compile("(sobid|агентский|агентские|скидки|агенство|риэлторские|вознагражд|агентство|комиссия|коммиссия|комиссион|коммисия|коммисия|скидка по комис|скидки по комис|комиссию|комиссия агенства)")
rOWNER = re.compile("(хозяина|хозяин|без комиссии|без агенства|агенства не|частное|агентам не|без посредников|не агенство)")
rPRICE = re.compile("(\D|^)\d{1,2}\W*\d00")
rOFFER_TYPE = re.compile("(сниму|снимем|снимет|арендуем|ищем|ищу \d-?к|ищу однок|ищу квартиру|ищу трехк)")
rAGENT_PERCENT = re.compile("\d\d%")

class MozillaEmulator(object):
    def __init__(self,cacher={},trycount=0):
        """Create a new MozillaEmulator object.

        @param cacher: A dictionary like object, that can cache search results on a storage device.
            You can use a simple dictionary here, but it is not recommended.
            You can also put None here to disable caching completely.
        @param trycount: The download() method will retry the operation if it fails. You can specify -1 for infinite retrying.
                A value of 0 means no retrying. A value of 1 means one retry. etc."""
        self.cacher = cacher
        self.cookies = cookielib.CookieJar()
        self.debug = False
        self.trycount = trycount
    def _hash(self,data):
        h = md5.new()
        h.update(data)
        return h.hexdigest()

    def build_opener(self,url,postdata=None,extraheaders={},forbid_redirect=False):
        txheaders = {
            'Accept':'text/xml,application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5',
            'Accept-Language':'ru,en;q=0.8,ru-ru;q=0.5,en-us;q=0.3',
            #            'Accept-Encoding': 'gzip, deflate',
            'Accept-Charset': 'utf-8,cp1251;q=0.7,*;q=0.7',
            'Keep-Alive': '300',
            'Connection': 'keep-alive',
#            'Cache-Control': 'max-age=0',
        }
        for key,value in extraheaders.iteritems():
            txheaders[key] = value
        req = urllib2.Request(url, postdata, txheaders)

        self.cookies.add_cookie_header(req)

        if forbid_redirect:
            redirector = HTTPNoRedirector()
        else:
            redirector = urllib2.HTTPRedirectHandler()

        http_handler = urllib2.HTTPHandler(debuglevel=self.debug)
        https_handler = urllib2.HTTPSHandler(debuglevel=self.debug)

        u = urllib2.build_opener(http_handler,https_handler, urllib2.HTTPCookieProcessor(self.cookies),redirector)
        u.addheaders = [('User-Agent','Opera/9.80 (X11; Linux i686; U; ja) Presto/2.7.62 Version/11.01')]


        if not postdata is None:
            req.add_data(postdata)
        return (req,u)

    def download(self,url,postdata=None,extraheaders={},forbid_redirect=False,
            trycount=None,fd=None,onprogress=None,only_head=False):
        """Download an URL with GET or POST methods.

        @param postdata: It can be a string that will be POST-ed to the URL.
            When None is given, the method will be GET instead.
        @param extraheaders: You can add/modify HTTP headers with a dict here.
        @param forbid_redirect: Set this flag if you do not want to handle
            HTTP 301 and 302 redirects.
        @param trycount: Specify the maximum number of retries here.
            0 means no retry on error. Using -1 means infinite retring.
            None means the default value (that is self.trycount).
        @param fd: You can pass a file descriptor here. In this case,
            the data will be written into the file. Please note that
            when you save the raw data into a file then it won't be cached.
        @param onprogress: A function that has two parameters:
            the size of the resource and the downloaded size. This will be
            called for each 1KB chunk. (If the HTTP header does not contain
            the content-length field, then the size parameter will be zero!)
        @param only_head: Create the openerdirector and return it. In other
            words, this will not retrieve any content except HTTP headers.

        @return: The raw HTML page data, unless fd was specified. When fd
            was given, the return value is undefined.
        """
        if trycount is None:
            trycount = self.trycount
        cnt = 0
        while True:
            try:
                key = self._hash(url)
                if (self.cacher is None) or (not self.cacher.has_key(key)):
                    req,u = self.build_opener(url,postdata,extraheaders,forbid_redirect)
                    openerdirector = u.open(req)
                    if self.debug:
                        print req.get_method(),url
                        print openerdirector.code,openerdirector.msg
                        print openerdirector.headers

                    self.cookies.extract_cookies(openerdirector,req)

                    if only_head:
                        return openerdirector
                    if openerdirector.headers.has_key('content-length'):
                        length = long(openerdirector.headers['content-length'])
                    else:
                        length = 0
                    dlength = 0
                    if fd:
                        while True:
                            data = openerdirector.read(1024)
                            dlength += len(data)
                            fd.write(data)
                            if onprogress:
                                onprogress(length,dlength)
                            if not data:
                                break
                    else:
                        data = ''
                        while True:
                            newdata = openerdirector.read(1024)
                            dlength += len(newdata)
                            data += newdata
                            if onprogress:
                                onprogress(length,dlength)
                            if not newdata:
                                break
                        #data = openerdirector.read()
                        if not (self.cacher is None):
                            self.cacher[key] = data
                else:
                    data = self.cacher[key]
                #try:
                #    d2= GzipFile(fileobj=cStringIO.StringIO(data)).read()
                #    data = d2
                #except IOError:
                #    pass
                return data
            except urllib2.URLError:
                cnt += 1
                if (trycount > -1) and (trycount < cnt):
                    raise
                # Retry :-)
                if self.debug:
                    print "MozillaEmulator: urllib2.URLError, retryting ",cnt


    def post_multipart(self,url,fields, files, forbid_redirect=True):
        """Post fields and files to an http host as multipart/form-data.
        fields is a sequence of (name, value) elements for regular form fields.
        files is a sequence of (name, filename, value) elements for data to be uploaded as files
        Return the server's response page.
        """
        content_type, post_data = encode_multipart_formdata(fields, files)
        result = self.download(url,post_data,{
            'Content-Type': content_type,
            'Content-Length': str(len(post_data))
        },forbid_redirect=forbid_redirect
        )
        return result


def format_phone(phone, remove_prefix = True):
    phone = rREPLACE.sub('', phone)

    if len(phone) >= 9 and rPHONE_PREFIX.match(phone):
        phone = rPHONE_PREFIX.sub('', phone)

    phone = re.sub("^0", '', phone)

    if remove_prefix:
        phone = rCITY_PREFIX.sub('', phone)

    return phone


class BaseAdParser:
    def __init__(self, url, region, content = None):
        self.url = url

        if not content:
            content = MozillaEmulator().download(self.url)

            content = content.decode(self.encoding(),'ignore')

            self.page = BeautifulSoup(content)
        else:
            self.page = content

        self.region = region

    def encoding(self):
        return 'utf-8'

    def date_format(self):
        return None

    def get_offer_type(self):
        return None

    def guess_address(self, content):
        metro = METRO_LIST[self.region]
        matches = []

        for metro_id, regexp in metro.items():
            if regexp[0].search(content):
                matches.append(metro_id)

        if len(matches) > 0:
            return matches


    def parse(self):
        self.title = re.sub(u"\n", "", self.get_title().strip().lower())

        self.content = self.get_content().lower().strip()

        self.md5 = self.get_md5(self.content)

        self.contact = self.get_contact().lower().strip()

        self.phone = self.get_phone()
        self.date = self.get_date()
        self.image = self.get_image()

        if self.__class__.__name__ == 'EmlsAdParser':
            self.contact = self.get_md5(self.contact)

        if type(self.date).__name__ == 'str' or type(self.date).__name__ == 'unicode':
            try:
                self.date == self.date.__str__()

                if self.date_format():
                    self.date = self.date.strip()
                    self.date = datetime.datetime.strptime(self.date, self.date_format())
                else:
                    self.date = parser.parse(self.date)
            except:
                self.date = None

        self.agent = self.is_agent()

        title = unicode(self.title).encode('utf-8', 'ignore')
        try:
            content = unicode(self.content).encode('utf-8', 'ignore')
        except:
            content = self.content

        contact = unicode(self.contact).encode('utf-8', 'ignore')

        content_for_search = "%s %s %s" % (content, contact, title)

        content_for_search = content_for_search.decode('utf-8').lower().encode('utf-8')

        self.is_real_agent = self.agent

        self.offer_type = self.get_offer_type()

        if rOFFER_TYPE.search(content_for_search):
            self.offer_type = 0
        else:
            self.offer_type = 1

        if rAGENT.search(content_for_search):
            self.is_real_agent = True

        if self.phone is None or rAGENT.search(content_for_search):
            self.agent = True
        else:
            if not self.agent and rOWNER.search(content_for_search):
                self.agent = False


        self.address = self.get_address().lower().encode('utf-8')

        self.address_id = self.guess_address(self.address)

        if self.address_id is None:
            self.address_id = []


        for addr in self.guess_address(content_for_search) or []:
            self.address_id.append(addr)

        self.address_id = list(set(self.address_id))

        if self.offer_type == 0 and len(self.address_id) == 0:
            self.address_id = ['all']

        if self.offer_type == 0 and rAGENT_PERCENT.search(content_for_search):
            self.agent_ready = True

        self.price = rPRICE.search(self.get_price().lower().encode('utf-8'))

        if self.price is None:
            self.price = rPRICE.search(content_for_search)

        if self.price:
            self.price = self.price.group(0)

            self.price = rREPLACE.sub('', self.price)

        print self.date
        print self.price
        print self.address_id
        print self.agent
        print self.is_real_agent
        print self.phone
        print self.image

        if self.offer_type == 1:
            print "sdam"
        else:
            print "snimu"

        if self.contact:
            self.contact = " ".join(self.contact.splitlines())

        return self

    def get_phone(self, expression = rMOBILE_PHONE):
        phone_match = expression.search(self.contact)

        if phone_match is None:
            phone_match = expression.search(self.content)

        if phone_match:
            return format_phone(phone_match.group(0))
        elif expression != rPHONE:
            return self.get_phone(rPHONE)

    def get_md5(self, content):
        md5 = hashlib.md5()
        try:
            content = unicode(content).encode('utf-8')
        except:
            pass
        md5.update(content)

        return md5.hexdigest()

    def get_address(self):
        return ""

    def get_price(self):
        return ""

    def get_image(self):
        return None

    def __str__(self):
        arr = []
        for attr in [self.agent, self.title, self.date, self.contact, self.phone, self.md5, self.url]:
            if attr is not None:
                try:
                    arr.append(unicode(attr).encode('utf-8', 'ignore'))
                except:
                    arr.append(str(attr))

        return ', '.join(arr)



class SlandoAdParser(BaseAdParser):
    MONTH = [[u"Января", "Jan"], [u"Февраля", "Feb"], [u"Марта", "Mar"], [u"Апреля", "Apr"], [u"Мая", "May"], [u"Июня","Jun"], [u"Июля","Jul"], [u"Августа","Aug"], [u"Сентября", "Sept"], [u"Октября", "Oct"], [u"Ноября","Nov"], [u"Декабря","Dec"]]

    def get_title(self):
        contents = self.page.find('h1').contents
        title = "".join([item.string or "" for item in contents])

        return title

    def get_name(self):
        return "slando"

    def get_image(self):
        try:
            return self.page.find('img', id='mainImage')['src']
        except:
            return None

    def get_contact(self):
        try:
            contacts = self.page.find('span', 'replacement').string

            if contacts is None:
                contacts = self.page.find('p', 'contacts').find('a').contents[0]

            return contacts
        except:
            return ""

    def get_content(self):
        arr = []

        content = self.page.find('p', 'copy').contents

        for tag in content:
            if tag.string:
                arr.append(tag.string)

        return u''.join(arr)

    def get_date(self):
        try:
            date = self.page.find('div', 'date').find('strong').string
            date = re.sub("[^\d]+", '', date, 1)
            date = unicode(date).encode('utf-8')

            for idx, month in enumerate(SlandoAdParser.MONTH):
                date = re.sub(unicode(month[0]).encode('utf-8'), month[1], date)

            return date
        except:
            return ""

    def get_price(self):
        try:
            content = self.page.find('div', 'r5 customfields').find('div','values').find('span')
            return content.string
        except:
            return ""

    def is_agent(self):
        try:
            is_agent = self.page.find('div', 'openpanel subcategories abscorners lightyellow').find('a', 'current')
            is_agent = is_agent.contents[0].strip().lower()

            return is_agent == u'квартиры от агентств'
        except:
            return ""


class AvitoAdParser(BaseAdParser):
    def get_title(self):
        return self.page.find('h1').string

    def get_name(self):
        return "avito"

    def get_contact(self):
        return self.page.find('dd', id='seller').find('strong').string

    def get_address(self):
        return " ".join([item.string or "" for item in self.page.find('dd', id='map').contents])

    def is_agent(self):
        try:
            user_type = self.page.find('dd', id='seller').find('span', 'grey').string
            return user_type == u"(компания)"
        except:
            return False

    def get_content(self):
        try:
            contents = self.page.find('dd', id='desc_text').contents
            return "".join([item.string or "" for item in contents])
        except:
            return ""

    def get_price(self):
        try:
            return self.page.find('span', 'price').find('strong').string
        except:
            return ""

    def get_phone(self):
        try:
            self.phone_key = self.page.find('input', id='phone_key')['value']
        except:
            self.phone_key = None

        return None

    def get_image(self):
        try:
            return self.page.find('td', 'big-picture more-than-one').find('img')['src']
        except:
            try:
                return self.page.find('td', 'big-picture only-one').find('img')['src']
            except:
                return None

    def get_date(self):
        date = self.page.find('dd', itemprop='priceValidUntil')['datetime']
        date = parser.parse(date)
        date = date + relativedelta(months=-2, days=2)

        return date


class OlxAdParser(BaseAdParser):
    MONTH = [[u"Январь", "Jan"], [u"Февраль", "Feb"], [u"Март", "Mar"], [u"Апрель", "Apr"], [u"Май", "May"], [u"Июнь","Jun"], [u"Июль","Jul"], [u"Август","Aug"], [u"Сентябрь", "Sept"], [u"Октябрь", "Oct"], [u"Ноябрь","Nov"], [u"Декабрь","Dec"]]

    def get_title(self):
        return self.page.find('p', id = 'olx_item_title').contents[3]

    def get_name(self):
        return "olx"

    def get_image(self):
        try:
            return self.page.find('img', id='obj_img')['src']
        except:
            pass

    def get_info(self, item, element = "item-data"):
        info = self.page.find('div', id = element).findAll('li')

        for i in info:
            title = i.contents[0].strip().lower()
            title = unicode(title)

            if title == item:
                return i.find('strong').string

    def get_contact(self):
        info = self.page.find('div', id = "item-data").findAll('li')
        info = " ".join([i.find('strong').string or "" for i in info])

        return info

    def get_address(self):
        return self.get_info(u"cт. метро / pайон:") or ""

    def get_price(self):
        return self.get_info(u"цена:") or ""

    def get_content(self):
        contents = self.page.find('div', id='description-text')

        return str(contents)

    def get_date(self):
        date = self.get_info(u"дата:")
        date = unicode(date).encode('utf-8')

        for idx, month in enumerate(OlxAdParser.MONTH):
            date = re.sub(unicode(month[0]).encode('utf-8'), month[1], date)

        return date

    def is_agent(self):
        try:
            return self.get_info(u"комиссия брокера:", "item-desc") == u"Да"
        except:
            return False


class EmlsAdParser(BaseAdParser):
    def get_title(self):
        return self.page.find('h1','h1-fullinfo').string

    def get_name(self):
        return "emls"

    def get_content(self):
        tds = self.page.findAll('td')
        for td in tds:
            if td.find('td'):
                continue

            link = td.find('a')

            if link and re.search("agent", link['href']):
                return td.contents[1]

    def is_agent(self):
        return True

    def get_contact(self):
        tds = self.page.findAll('td', colspan='2')
        for td in tds:
            if td.find('strong'):
                contents = td.contents
                return "".join([item.string or "" for item in contents])

    def get_date(self):
        return ""


class IrrAdParser(BaseAdParser):
    def get_title(self):
        return self.page.find('div', 'w-title').find('b').string

    def get_name(self):
        return "irr"

    def get_price(self):
        try:
            return "".join([item.string for item in self.page.find('span', 'or-d').contents])
        except:
            pass

    def get_content(self):
        try:
            return " ".join(self.page.find('div', 'brd-md additional-text').findAll(text=True))
        except:
            return ""

    def is_agent(self):
        return False

    def get_contact(self):
        try:
            contents = self.page.find('div', 'brd-md contacts-info').find('li', 'ico-phone')
            return "".join([item.string or "" for item in contents])
        except:
            try:
                contents = self.page.find('div', 'brd-md contacts-info').find('li', 'ico-mphone')
                return "".join([item.string or "" for item in contents])
            except:
                try:
                    contents = self.page.find('div', 'brd-md contacts-info').find('li', 'ico-icq')
                    return "".join([item.string or "" for item in contents])
                except:
                    return ""

    def get_date(self):
        timestamp = self.page.find('li', id = "ad_date_create").string
        return datetime.datetime.fromtimestamp(int(timestamp))


class OneGSAdParser(BaseAdParser):
    def date_format(self):
        return "%d.%m.%y %H:%M"

    def encoding(self):
        return "cp1251"

    def get_title(self):
        contents = self.page.find('div',"posttitle sel0").contents

        return "".join([item.string or "" for item in contents])

    def get_name(self):
        return "1gs"

    def get_contact(self):
        contents = self.page.find('div', 'boxphone').contents

        return "".join([item.string or "" for item in contents])

    def is_agent(self):
        return False

    def get_content(self):
        contents = self.page.find('div', "posttext").contents

        return "".join([item.string or "" for item in contents])

    def get_date(self):
        return str(self.page.find('div', 'time').contents[0].string)


class VkontakteAdParser(BaseAdParser):
    def encoding(self):
        return "cp1251"

    def __init__(self, url, region):
        self.url = url

        browser = vk_browser()

        content = browser.download(url)

        self.content = content.decode(self.encoding(), 'ignore')

        self.page = BeautifulSoup(self.content)

        self.region = region

    def get_title(self):
        contents = self.page.find('div',"title").contents

        return "".join([item.string or "" for item in contents])

    def get_name(self):
        return "vkontakte"

    def get_contact(self):
        return ""

    def get_image(self):
        try:
            return self.page.find("div", "photos").find('a')['href']
        except:
            return None

    def get_price(self):
        try:
            contents = self.page.find('div', "price").contents
            return "".join([item.string or "" for item in contents])
        except:
            return ""

    def is_agent(self):
        return False

    def get_content(self):
        contents = self.page.find('div', "description").contents
        contents = "".join([item.string or "" for item in contents])

        info = "".join(self.page.find('div', "info").findAll(text = True))

        return contents + info

    def get_address(self):
        return "".join(self.page.find('div', "info").findAll(text = True))


    def get_date(self):
        contents = self.page.find('div', "category").contents

        contents = "".join([item.string or "" for item in contents])
        contents = contents.lower()

        rTODAY = re.compile(u"сегодня")
        rYESTERDAY = re.compile(u"вчера")
        rVKDATE = re.compile(u"опубликовано (\d+)\s(\D+)\s(\d+)")

        if re.search(rTODAY, contents):
            return datetime.datetime.today()
        elif re.search(rYESTERDAY, contents):
            return datetime.datetime.today() - relativedelta(days=1)
        else:
            date = re.search(rVKDATE, contents)

            for idx, month in enumerate(SlandoAdParser.MONTH):
                if date.group(2).encode('utf-8') == month[0].lower().encode('utf-8'):
                    return "%s %s %s" % (date.group(1), month[1], date.group(3))


class NovoebenevoAdParser(BaseAdParser):
    def date_format(self):
        return "%d.%m.%Y"

    def get_title(self):
        return "".join(self.page.find('div',"header noIntoTab").findAll(text=True))

    def get_name(self):
        return "novoebenevo"

    def get_contact(self):
        return ""

    def is_agent(self):
        return False

    def get_address(self):
        return " ".join(self.page.find('li', 'metro').findAll(text=True))

    def get_price(self):
        return " ".join(self.page.find('li', 'cost embossed').findAll(text=True))

    def get_content(self):
        return " ".join(self.page.find('dl', 'flatInfo').findAll(text=True))

    def get_date(self):
        return self.page.find('li', 'date').string.replace(u"г.", "")


class EgentAdParser(BaseAdParser):
    def encoding(self):
        return "cp1251"

    def get_title(self):
        return "".join(self.page.find('div',"header").find('strong').findAll(text=True))

    def get_name(self):
        return "egent"

    def get_contact(self):
        return " ".join(self.page.find('div', 'userinfo gray').findAll(text=True))

    def is_agent(self):
        return False

    def get_address(self):
        return " ".join(self.page.find('div', 'adres').findAll(text=True))

    def get_price(self):
        return " ".join(self.page.find('div', 'price').findAll(text=True))

    def get_content(self):
        return " ".join(self.page.find('div', 'desc').findAll(text=True))

    def get_date(self):
        try:
            container = "".join(self.page.find('div', "item detail").findAll('td')[-1].find('div').findAll(text=True))

            rDATE = re.compile("(\d\d)\s(\D+)\s(\d\d\d\d)")

            date = re.search(rDATE, container)

            for idx, month in enumerate(SlandoAdParser.MONTH):
                if date.group(2).lower() == month[0].lower():
                    return "%s %s %s" % (date.group(1), month[1], date.group(3))
        except:
            return datetime.datetime.now()



rAVITO = re.compile("avito.ru")
rSLANDO = re.compile("(slando.spb.ru|slando.ru)")
rOLX = re.compile("olx.ru")
rARENDA_OPEN = re.compile("arenda-open.ru")
rEMLS = re.compile("emls.ru")
rIRR = re.compile("irr.ru")
rOneGS = re.compile("1gs.ru")
rVkontakte = re.compile("vkontakte.ru")
rNovoebenevo = re.compile("novoebenevo.ru")
rEgent = re.compile("egent.ru")

def parser_name(url):
    if rAVITO.search(url):
        return "avito"
    elif rSLANDO.search(url):
        return "slando"
    elif rOLX.search(url):
        return "olx"
    elif rARENDA_OPEN.search(url):
        return "arenda-open"
    elif rEMLS.search(url):
        return "emls"
    elif rIRR.search(url):
        return "irr"
    elif rOneGS.search(url):
        return "1gs"
    elif rVkontakte.search(url):
        return "vkontakte"
    elif rNovoebenevo.search(url):
        return "novoebenevo"
    elif rEgent.search(url):
        return "egent"


def parse(url, region):
    if rAVITO.search(url):
        result = AvitoAdParser(url, region).parse()
    elif rSLANDO.search(url):
        result = SlandoAdParser(url, region).parse()
    elif rOLX.search(url):
        result = OlxAdParser(url, region).parse()
    elif rARENDA_OPEN.search(url):
        result = ArendaOpenAdParser(url, region).parse()
    elif rEMLS.search(url):
        result = EmlsAdParser(url, region).parse()
    elif rIRR.search(url):
        result = IrrAdParser(url, region).parse()
    elif rOneGS.search(url):
        result = OneGSAdParser(url, region).parse()
    elif rVkontakte.search(url):
        result = VkontakteAdParser(url, region).parse()
    elif rNovoebenevo.search(url):
        result = NovoebenevoAdParser(url, region).parse()
    elif rEgent.search(url):
        result = EgentAdParser(url, region).parse()

    logging.info(url)
    return result



class SiteParser:
    def __init__(self, url, page_number = 1):
        self.base_url = url
        self.page_number = page_number

        self.url = self.get_paged_url()

        content = MozillaEmulator().download(self.url)

        content = re.sub("<noindex\/?>", "", content)

        self.page = BeautifulSoup(content)

    def parse(self):
        links = self.get_list()

        return set(links)


rRENT_LINKS = re.compile(u'(домик|домики|часы|сут\.|садовый дом|дома|помогу|дача|дачу|гостиница|отл дом|дом на лето|сдам дом|аренда дома|коттедж|номер)')


def make_cookie_header(cookie):
    ret = ""
    for val in cookie.values():
        ret+="%s=%s; "%(val.key, val.value)
    return ret

_vk_browser = None

def vk_browser():
    global _vk_browser

    if _vk_browser:
        return _vk_browser

    _vk_browser = MozillaEmulator()
    _vk_browser.download("https://login.vk.com", "act=login&q=&al_frame=1&expire=&captcha_sid=&captcha_key=&from_host=vkontakte.ru&email=79052652181&pass=97gubuga")

    return _vk_browser



class VkontakteParser:
    def __init__(self, url, page_number = 1):

        self.base_url = url
        self.page_number = page_number

        url = self.get_paged_url()

        browser = vk_browser()

        self.content = browser.download(url)

    def parse(self):
        ads = []

        rLINKS = re.compile("act=view&id=(\d+)")

        for match in re.finditer(rLINKS, self.content):
            link = "http://vkontakte.ru/market.php?act=view&id=%s" % match.group(1)

            ads.append(link)

        return set(ads)

    def get_paged_url(self):
        return "%s&offset=%d" % (self.base_url, (self.page_number-1)*40)


rURL_PARAMS = re.compile("([^?]+)\?([^?]+)")

class AvitoParser(SiteParser):
    def get_paged_url(self):
        url = rURL_PARAMS.match(self.base_url)

        return "%s/page%d?%s" % (url.group(1), self.page_number, url.group(2))

    def get_list(self):
        ads = []
        links = self.page.findAll("h3", "t_i_h3")

        for link in links:
            link = link.find('a')

            if rRENT_LINKS.search(link.string.lower().strip()) is None:
                ads.append("http://www.avito.ru"+link['href'])

        return ads


class SlandoParser(SiteParser):
    rPAGE = re.compile("\d\.html$")

    def get_paged_url(self):
        return SlandoParser.rPAGE.sub("%d.html" % self.page_number, self.base_url)

    def get_list(self):
        ads = []
        links = self.page.findAll("a", "desc preserve_search_term")

        for link in links:
            contents = "".join([item.string or "" for item in link.contents])

            if contents and rRENT_LINKS.search(contents.lower().strip()) is None:
                ads.append(link['href'])

        return ads

class OneGsParser(SiteParser):
    def get_paged_url(self):
        return "%s?part=%d" % (self.base_url, self.page_number)

    def get_list(self):
        ads = []
        containers = self.page.findAll("div", "posttitle sel0")

        for div in containers:
            ads.append(div.find("a")['href'])

        return ads


class OlxParser(SiteParser):
    def get_paged_url(self):
        return self.base_url + "-p-%d" % self.page_number

    def get_list(self):
        ads = []
        links = self.page.findAll("div", "c-2 listing-profile")

        for link in links:
            a = link.find('a')

            if rRENT_LINKS.search(a.string.strip().lower()) is None:
                ads.append(link.find('a')['href'])

        return ads


class ArendaOpenParser(SiteParser):
    def get_paged_url(self):
        return self.base_url

    def get_list(self):
        ads = []
        links = self.page.findAll('a')

        for link in links:
            if re.search('page=company', link['href']):
                ads.append("http://arenda-open.ru%s" % link['href'])

        return ads


class EmlsMainParser(SiteParser):
    def get_paged_url(self):
        return self.base_url

    def get_list(self):
        ads = []
        links = self.page.findAll('a')

        for link in links:
            try:
                if re.search('flats', link['href']):
                    ads.append("http://www.emls.ru%s" % link['href'])
            except:
                pass

        return ads


class EmlsParser(SiteParser):
    def get_paged_url(self):
        return re.sub("flats/", "flats/page%d.html" % self.page_number, self.base_url)

    def get_list(self):
        ads = []
        links = self.page.findAll('a')

        for link in links:
            try:
                if re.search('fullinfo', link['href']):
                    ads.append("http://www.emls.ru%s" % link['href'])
            except:
                pass

        return ads


class IrrParser(SiteParser):
    def get_paged_url(self):
        return re.sub("page1", "page%d" % self.page_number, self.base_url)

    def get_list(self):
        ads = []
        links = self.page.findAll('a')

        for link in links:
            if re.search('advert/', link['href']) and not re.search('location', link['href']):
                contents = link.contents
                contents = "".join([item.string or "" for item in contents])

                if rRENT_LINKS.search(contents.lower().strip()) is None:
                    ads.append("http://www.irr.ru%s" % link['href'])

        return ads


class NovoebenevoParser(SiteParser):
    def get_paged_url(self):
        return "%s/page_%d" % (self.base_url, self.page_number)

    def get_list(self):
        ads = []
        links = self.page.findAll('a', 'more')

        for link in links:
            ads.append("http://www.novoebenevo.ru%s" % link['href'])

        return ads

class EgentParser(SiteParser):
    def get_paged_url(self):
        return "%s&p=%d" % (self.base_url, (self.page_number-1)*20)

    def get_list(self):
        ads = []
        links = self.page.findAll('div', 'header')

        for link in links:
            ads.append(link.find('a')['href'])

        return ads


def ads_list(url, page = 1):
    if rAVITO.search(url):
        return AvitoParser(url, page)
    elif rSLANDO.search(url):
        return SlandoParser(url, page)
    elif rOLX.search(url):
        return OlxParser(url, page)
    elif rARENDA_OPEN.search(url):
        return ArendaOpenParser(url, page)
    elif rEMLS.search(url):
        return EmlsParser(url, page)
    elif rIRR.search(url):
        return IrrParser(url, page)
    elif rOneGS.search(url):
        return OneGsParser(url, page)
    elif rVkontakte.search(url):
        return VkontakteParser(url, page)
    elif rNovoebenevo.search(url):
        return NovoebenevoParser(url, page)
    elif rEgent.search(url):
        return EgentParser(url, page)

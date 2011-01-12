# coding: utf-8

from google.appengine.api import xmpp
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from RtmBot import RtmBot
import Config
from SecureStorage import SecureStorage
import logging
import re

class XMPPHandler(webapp.RequestHandler):
    def post(self):
        message = xmpp.Message(self.request.POST)
        
        storage = SecureStorage(re.sub(r"/.+$", "",message.sender))
        
        bot = RtmBot(Config.API_KEY, Config.API_SECRET, Config.ADMIN_JID, storage)
        message.reply(bot.processCommand(message.body))

application = webapp.WSGIApplication([('/_ah/xmpp/message/chat/', XMPPHandler)],
                                     debug=True)

def main():
    logging.getLogger().setLevel(logging.DEBUG)

    run_wsgi_app(application)

if __name__ == "__main__":
    main()

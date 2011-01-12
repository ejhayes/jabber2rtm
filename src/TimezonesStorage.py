# coding: utf-8

from google.appengine.ext.db import Model, TextProperty, DateTimeProperty
import simplejson
import datetime

class TimezoneStorageModel(Model):
    data = TextProperty()
    lastUpdated = DateTimeProperty(auto_now = True)
    
def getTimezones(rtmApi):
    model = TimezoneStorageModel.get_or_insert("2")
    
    if (datetime.datetime.now() - model.lastUpdated).seconds > 3600:
        model.data = None

    if model.data == None:
        aTimezonesRaw = rtmApi.timezonesGetList(raw = True)
        model.data = simplejson.dumps(aTimezonesRaw)
        model.put()
    else:
        aTimezonesRaw = simplejson.loads(model.data)
        
    aTimezones = rtmApi.timezonesGetList(fromRaw = aTimezonesRaw)
    
    return aTimezones


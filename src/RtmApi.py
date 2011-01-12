# coding: utf-8

import urllib
from hashlib import md5
import re
import time
import simplejson
from google.appengine.api import urlfetch
import random
import calendar

class RtmApiException(Exception):
    pass

class RtmApi(object):
    AUTH_URL = "http://www.rememberthemilk.com/services/auth/"
    REST_URL = "http://api.rememberthemilk.com/services/rest/"
    TIMEOUT = 30
    
    PERMS_READ = "read"
    PERMS_WRITE = "write"
    PERMS_DELETE = "delete"
    
    __aNeedAuth = ("rtm.timelines.create", "rtm.tasks.add", "rtm.tasks.delete", "rtm.tasks.notes.add", "rtm.tasks.getList",
                                "rtm.lists.getList", "rtm.tasks.complete", "rtm.tasks.delete", "rtm.tasks.postpone", "rtm.tasks.addTags",
                                "rtm.tasks.removeTags", "rtm.tasks.moveTo", "rtm.settings.getList")
    
    __aNeedTimeline = ("rtm.tasks.add", "rtm.tasks.delete", "rtm.tasks.notes.add", "rtm.tasks.complete", "rtm.tasks.delete",
                                    "rtm.tasks.postpone", "rtm.tasks.addTags", "rtm.tasks.removeTags", "rtm.tasks.moveTo")
    
    def __init__(self, apiKey, secret):
        self.__apiKey = apiKey
        self.__secret = secret
        self.__authToken = None
        self.__timeline = None
        
        # for local debug set it to True
        self.localDebug = False
    
    def testEcho(self):
        """@link http://www.rememberthemilk.com/services/api/methods/rtm.test.echo.rtm"""
        
        return self.__request("rtm.test.echo")
    
    def testLogin(self):
        """@link http://www.rememberthemilk.com/services/api/methods/rtm.test.echo.rtm"""
        return self.__request("rtm.test.login")
    
    def getFrob(self):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.auth.getFrob.rtm
        @return string frob
        """

        o = self.__request("rtm.auth.getFrob")
        return o["rsp"]["frob"]
    
    def getDesktopAuthUrl(self, perms, frob):
        aRequest = {"perms": perms, "frob": frob, "api_key": self.__apiKey}
        
        aRequest = self.__signRequest(aRequest)
        
        params = ["%s=%s" % (name, aRequest[name].encode("utf-8")) for name in aRequest]
        
        return RtmApi.AUTH_URL + "?" + "&".join(params)
    
    def getToken(self, frob):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.auth.getToken.rtm
        @param string $frob
        @return array
        """
        
        o = self.__request("rtm.auth.getToken", {"frob": frob})
        return o["rsp"]["auth"]
    
    def checkToken(self, token):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.auth.checkToken.rtm
        @param string $token
        """
        
        o = self.__request("rtm.auth.checkToken", {"auth_token": token})
        return o["rsp"]["auth"]
    
    def setAuthToken(self, token):
        self.__authToken = token
    
    def beginTimeline(self):
        """@link http://www.rememberthemilk.com/services/api/methods/rtm.timelines.create.rtm"""
        
        o = self.__request("rtm.timelines.create")
        
        self.__timeline = o["rsp"]["timeline"]
    
    def taskAdd(self, name, parse = False, listId = None):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.tasks.add.rtm
        @param string $name
        @param boolean $parse
        @param int listId
        @return RtmApiTaskseria
        """
        
        aRequest = {"name": name}
        if parse:
            aRequest["parse"] = u"1"
        
        if listId != None:
            aRequest["list_id"] = listId
        
        o = self.__request("rtm.tasks.add", aRequest)
        
        return RtmApiList.createFromRaw(o["rsp"]["list"])
    
    def taskNoteAdd(self, title, text, listId, taskseriesId, taskId):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.tasks.notes.add.rtm
        @param string $title
        @param string $text
        @param int listId
        @param int $taskseriesId
        @param int $taskId
        """

        aRequest = {"note_title": title, "note_text": text, "list_id": listId, "taskseries_id": taskseriesId, "task_id": taskId}
        
        o = self.__request("rtm.tasks.notes.add", aRequest)
        return o["rsp"]["note"]
    
    def taskGetList(self, listId = None, filter = None, lastSync = None):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.tasks.getList.rtm
        
        @param int|None listId The id of the list to perform an action on
        @param string $filter If specified, only tasks matching the desired criteria are returned. See http://www.rememberthemilk.com/help/answers/search/advanced.rtm
        @param string $lastSync An ISO 8601 formatted time value. If last_sync is provided, only tasks modified since last_sync will be returned, 
                                and each element will have an attribute, current, equal to last_sync.
        @return RtmApiList[]
        """
        
        aRequest = {}
        if listId != None:
            aRequest["list_id"] = listId
        
        if filter != None:
            aRequest["filter"] = filter
        
        if lastSync != None:
            aRequest["last_sync"] = lastSync
        
        o = self.__request("rtm.tasks.getList", aRequest)
        
        aList = []
        if "list" in o["rsp"]["tasks"] and len(o["rsp"]["tasks"]["list"]) > 0:
            if not is_array(o["rsp"]["tasks"]["list"]):
                o["rsp"]["tasks"]["list"] = [o["rsp"]["tasks"]["list"]]
            
            aList = [RtmApiList.createFromRaw(list) for list in o["rsp"]["tasks"]["list"]]
        
        return aList
    
    def taskComplete(self, listId, taskseriesId, taskId):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.tasks.complete.rtm
        @param int listId
        @param int $taskseriesId
        @param int $taskId
        @return RtmApiList
        """
                
        aRequest = {"list_id": listId, "taskseries_id": taskseriesId, "task_id": taskId}
        
        o = self.__request("rtm.tasks.complete", aRequest)
        return RtmApiList.createFromRaw(o["rsp"]["list"])
    
    def taskDelete(self, listId, taskseriesId, taskId):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.tasks.delete.rtm
        @param int listId
        @param int $taskseriesId
        @param int $taskId
        @return RtmApiList
        """
        aRequest = {"list_id": listId, "taskseries_id": taskseriesId, "task_id": taskId}
        
        o = self.__request("rtm.tasks.delete", aRequest)
        return RtmApiList.createFromRaw(o["rsp"]["list"])
    
    def taskPostpone(self, listId, taskseriesId, taskId):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.tasks.postpone.rtm
        @param int listId
        @param int $taskseriesId
        @param int $taskId
        @return RtmApiList
        """
        
        aRequest = {"list_id": listId, "taskseries_id": taskseriesId, "task_id": taskId}
        
        o = self.__request("rtm.tasks.postpone", aRequest)
        return RtmApiList.createFromRaw(o["rsp"]["list"])
    
    def taskAddTags(self, listId, taskseriesId, taskId, tags):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.tasks.addTags.rtm
        @param int listId
        @param int $taskseriesId
        @param int $taskId
        @param string $tags A comma delimited list of tags
        @return RtmApiList
        """
        
        aRequest = {"list_id": listId, "taskseries_id": taskseriesId, "task_id": taskId, "tags": tags}
        
        o = self.__request("rtm.tasks.addTags", aRequest)
        return RtmApiList.createFromRaw(o["rsp"]["list"])
    
    def taskRemoveTags(self, listId, taskseriesId, taskId, tags):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.tasks.removeTags.rtm
        @param int listId
        @param int $taskseriesId
        @param int $taskId
        @param string $tags A comma delimited list of tags
        @return RtmApiList
        """
        
        aRequest = {"list_id": listId, "taskseries_id": taskseriesId, "task_id": taskId, "tags": tags}
        
        o = self.__request("rtm.tasks.removeTags", aRequest)
        return RtmApiList.createFromRaw(o["rsp"]["list"])
    
    def taskMoveTo(self, fromListId, taskseriesId, taskId, toListId):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.tasks.moveTo.rtm
        @param $fromListId
        @param $taskseriesId
        @param $taskId
        @param $toListId
        @return RtmApiList
        """
        
        aRequest = {"from_list_id": fromListId, "taskseries_id": taskseriesId, "task_id": taskId, "to_list_id": toListId}
        
        o = self.__request("rtm.tasks.moveTo", aRequest)
        return RtmApiList.createFromRaw(o["rsp"]["list"])
    
    def listGetList(self):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.lists.getList.rtm
        @return RtmApiList[]
        """

        o = self.__request("rtm.lists.getList")
        
        aList = []
        for data in o["rsp"]["lists"]["list"]:
            aList.append(RtmApiList.createFromRaw(data))
        
        return aList
    
    def timezonesGetList(self, raw = False, fromRaw = None):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.timezones.getList.rtm
        @return RtmApiTimezone[]
        """

        if not fromRaw:
            o = self.__request("rtm.timezones.getList")
            
            if (raw):
                return o["rsp"]["timezones"]["timezone"]
            
            rawList = o["rsp"]["timezones"]["timezone"]
        else:
            rawList = fromRaw
        
        aList = []
        for data in rawList:
            aList.append(RtmApiTimezone.createFromRaw(data))
        
        return aList
    
    def settingsGetList(self):
        """
        @link http://www.rememberthemilk.com/services/api/methods/rtm.settings.getList.rtm
        @return RtmApiSettings
        """
        o = self.__request("rtm.settings.getList")
        return RtmApiSettings.createFromRaw(o["rsp"]["settings"])
    
    def __request(self, method, aRequest = None):
        
        if aRequest == None:
            aRequest = {}
        
        # add common request parameters
        
        aRequest["api_key"] = self.__apiKey
        aRequest["method"] = method
        aRequest["format"] = "json"
        
        # add auth token if needed
        if self.__authToken != None and method in RtmApi.__aNeedAuth:
            aRequest["auth_token"] = self.__authToken
        
        
        # add timeline if needed
        if self.__timeline != None and method in RtmApi.__aNeedTimeline:
            aRequest["timeline"] = self.__timeline
        
        # convert request to utf-8
        aRequestUtf8 = {}
        for name in aRequest:
            if isinstance(aRequest[name], unicode):
                aRequestUtf8[name] = aRequest[name].encode("utf-8")
            else:
                aRequestUtf8[name] = aRequest[name]
        aRequest = aRequestUtf8
        
        if self.localDebug:
            aRequest["rnd"] = str(random.randint(1000000, 99999999))
        
        # sign the request
        aRequest = self.__signRequest(aRequest)
        
        # make HTTP call

        if self.localDebug:
            url = RtmApi.REST_URL
            if len(aRequest) > 0:
                url = url + '?' + urllib.urlencode(aRequest)
            jsonResult = urllib.urlopen(url).read()
        else:
            jsonResult = urlfetch.fetch(url = RtmApi.REST_URL, payload = urllib.urlencode(aRequest), method = urlfetch.POST,
                                        headers = {'Content-Type': 'application/x-www-form-urlencoded'}, deadline = RtmApi.TIMEOUT).content
        
        # decode JSON
        result = simplejson.loads(jsonResult)
        
        # analyze for errors
        if "rsp" in result and "stat" in result["rsp"] and result["rsp"]["stat"] == "fail":
            raise RtmApiException(result["rsp"]["err"]["msg"], result["rsp"]["err"]["code"])
        
        return result
    
    def __signRequest(self, aRequest):
        """
        @link http://www.rememberthemilk.com/services/api/authentication.rtm
        @param array $aRequest
        @return array
        """
        keys = aRequest.keys()
        keys.sort()
        
        s = ""
        for name in keys:
            s += name + aRequest[name]
            
        aRequest["api_sig"] = md5(self.__secret + s).hexdigest()
        
        return aRequest

class RtmApiObject:
    def __repr__(self):
        return self.toString()

class RtmApiTaskseria(RtmApiObject):
    @classmethod
    def createFromRaw(cls, data, listId = None):
        taskSeria = RtmApiTaskseria()
        taskSeria.id = data["id"]
        taskSeria.created = data["created"]
        taskSeria.modified = data["modified"]
        taskSeria.name = data["name"]
        taskSeria.source = data["source"]
        taskSeria.url = data["url"]
        taskSeria.location_id = data["location_id"]
        
        taskSeria.listId = listId
        
        if "rrule" in data:
            taskSeria.rrule = RtmApiRrule.createFromRaw(data["rrule"])
        else:
            taskSeria.rrule = None
        
        if "tag" in data["tags"]:
            if not is_array(data["tags"]["tag"]):
                taskSeria.tags = [data["tags"]["tag"]]
            else:
                taskSeria.tags = data["tags"]["tag"]
        else:
            taskSeria.tags = []
        
        taskSeria.participants = data["participants"]
        
        taskSeria.notes = []
        if "note" in data["notes"]:
            if not is_array(data["notes"]["note"]):
                data["notes"]["note"] = [data["notes"]["note"]]
            
            for aNote in data["notes"]["note"]:
                taskSeria.notes.append(RtmApiNote.createFromRaw(aNote))
        
        taskSeria.task = RtmApiTask.createFromRaw(data["task"])
        
        return taskSeria
    
    def toString(self, userSettings = None):
        aResult = []
        
        if (self.task.completed != ""):
            aResult.append(u"[+]")
        
        if (self.task.deleted):
            aResult.append(u"[x]")
        
        aResult.append(self.name)
        
        if (self.url != ""):
            aResult.append(u"[" + self.url + "]")
        
        if len(self.tags) > 0:
            for tag in self.tags:
                aResult.append(u"#" + tag)
        
        if self.task.due != "":
            dueTime = time.strptime(self.task.due, u"%Y-%m-%dT%H:%M:%SZ")
            
            timestamp = calendar.timegm(dueTime)
            diff = timestamp - time.mktime(time.gmtime())
            
            inUserTimezone = userSettings != None
            
            # convert datetime to user's timezone
            if inUserTimezone:
                dueTime = time.gmtime(userSettings.getTimezone().gmtToUser(timestamp))
            
            weekDays = (u"Sunday", u"Monday", u"Tuesday", u"Wednsday", u"Thursday", u"Friday", u"Saturday")
            months = (u"January", u"Febuary", u"March", u"April", u"May", u"June", u"July", u"August", u"September", u"October", u"November", u"December")
            
            theDate = time.strftime(u"%Y-%m-%d", dueTime)
            if theDate == time.strftime(u"%Y-%m-%d"):
                theDate = u"today"
            elif diff > 0 and diff < 24*3600*7:
                theDate = weekDays[int(time.strftime("%w", dueTime))]
            elif time.strftime("%Y", dueTime) == time.strftime("%Y"):
                theDate = months[int(time.strftime("%m", dueTime))] + u" " + time.strftime(u"%d", dueTime)
            
            if inUserTimezone:
                theTime = time.strftime(u"%H:%M", dueTime)
            else:
                theTime = time.strftime(u"%H:%M GMT", dueTime)
            
            if self.task.has_due_time:
                aResult.append(u"^" + theDate + " " + theTime)
            else:
                aResult.append(u"^" + theDate)
        
        if self.task.estimate != "":
            aResult.append(u"=" + self.task.estimate)
        
        if self.rrule != None:
            aResult.append(u"*" + str(self.rrule))
        
        if (self.task.priority != "N"):
            aResult.append(u"!" + self.task.priority)
        
        if len(self.notes) > 0:
            aResult.append(u"\n\n" + u"\n\n".join(map(RtmApiNote.toString, self.notes)))
            
        #aResult.append(" " + self.getFullTaskId())
        
        return " ".join(aResult)
    
    def getFullTaskId(self):
        return u"#" + self.listId + u"-" + self.id + u"-" + self.task.id
    
class RtmApiTask(RtmApiObject):
    @classmethod
    def createFromRaw(cls, data):
        task = RtmApiTask()
        task.id = data["id"]
        task.due = data["due"]
        task.has_due_time = data["has_due_time"] == u"1"
        task.added = data["added"]
        task.completed = data["completed"]
        task.deleted = data["deleted"]
        task.priority = data["priority"]
        task.postponed = data["postponed"]
        task.estimate = data["estimate"]
        
        return task

class RtmApiNote(RtmApiObject):
    @classmethod
    def createFromRaw(cls, data):
        note = RtmApiNote()
        note.id = data["id"]
        note.created = data["created"]
        note.modified = data["modified"]
        note.title = data["title"]
        note.text = data["$t"]
        
        return note
    
    def toString(self):
        if self.title != "":
            return self.title + u"\n" + self.text
        else:
            return self.text

class RtmApiRrule(RtmApiObject):
    @classmethod
    def createFromRaw(cls, data):
        rrule = RtmApiRrule()
        rrule.every = data["every"]
        rrule.rule = data["$t"]
        
        return rrule
    
    def toString(self):
        ruleParts = {
            "FREQ" : "",
            "INTERVAL" : "",
            "BYDAY" : "",
            "BYMONTHDAY" : ""
        }
        
        aRulePars = self.rule.split(u";")
        for pair in aRulePars:
            parts = pair.split(u"=")
            ruleParts[parts[0]] = parts[1]
        
        # make 'monthly' 'month' and 'daily': 'day'
        pluralToSingular = ((u"monthly", u"month"), (u"daily", u"day"), (u"yearly", u"year"), (u"weekly", u"week"))
        ruleParts["FREQ"] = ruleParts["FREQ"].lower()
        for plural, singular in pluralToSingular:
            ruleParts["FREQ"] = re.sub(plural, singular, ruleParts["FREQ"])
        
        s = []
        
        if (self.every == 1):
            s.append(u"every " + ruleParts["INTERVAL"] + u" " + ruleParts["FREQ"].lower() + (int(ruleParts["INTERVAL"]) > 1 and u"s" or u""))
        else:
            s.append(u"after " + ruleParts["INTERVAL"] + u" " + ruleParts["FREQ"].lower() + (int(ruleParts["INTERVAL"]) > 1 and u"s" or u""))
        
        if (ruleParts["BYDAY"] != ""):
            aMatches = re.match(ur"^(\d)(..)$", ruleParts["BYDAY"]).groups()
            s.append(u"on the " + self.__makeNumeral(aMatches[0]) + u" " + self.__makeReadableWeekday(aMatches[1]))
        
        if (ruleParts["BYMONTHDAY"] != ""):
            s.append(u"on the " + self.__makeNumeral(ruleParts["BYMONTHDAY"]))
        
        return " ".join(s)
    
    def __makeNumeral(self, number):
        number = str(number)
        
        lastDigit = number[-1]
        
        if lastDigit == "1":
            number += u"st"
        elif lastDigit == "2":
            number += u"nd"
        elif lastDigit == "3":
            number += u"rd"
        else:
            number += u"th"
        
        return number
    
    def __makeReadableWeekday(self, name):
        pairs = ((u"MO", u"Monday"), (u"TU", u"Tuesday"), (u"TH", u"Thursday"), (u"FR", u"Friday"), (u"SA", u"Saturday"), (u"SU", u"Sunday"))
        
        for short, long in pairs:
            name = re.sub(short, long, name)
            
        return name

class RtmApiList(RtmApiObject):
    
    @classmethod
    def createFromRaw(cls, data):
        list = RtmApiList()
        list.id = data["id"]
        list.aTaskseries = None
        list.name = None
        
        if "taskseries" in data:
            list.aTaskseries = []

            if  not is_array(data["taskseries"]):
                data["taskseries"] = [data["taskseries"]]

            for taskseriaData in data["taskseries"]:
                list.aTaskseries.append(RtmApiTaskseria.createFromRaw(taskseriaData, list.id))
        elif "name" in data:
            list.name = data["name"]
            list.deleted = data["deleted"]
            list.locked = data["locked"]
            list.archived = data["archived"]
            list.position = data["position"]
            list.smart = data["position"]
            if "filter" in data:
                list.filter = data["filter"]
            else:
                list.filter = None
            list.sort_order = data["sort_order"]
        else:
            list.aTaskseries = []
        
        return list
    
    def toString(self):
        if self.name != None:
            return u"(id: %s, name: %s, deleted: %s, locked: %s, archived: %s, position: %s, smart: %s, filter: %s, sort_order: %s)" % (self.id, self.name, self.deleted, self.locked, self.archived, self.position, self.smart, self.filter, self.sort_order)
        else:
            return u"(id: %s, tasks: %s)" % (self.id, map(RtmApiTaskseria.toString, self.aTaskseries))
    
    def getTaskseries(self):
        if (self.aTaskseries == None):
            raise RtmApiException("The list has no attached taskseries")
        else:
            return self.aTaskseries
        
class RtmApiTimezone:
    aTimezones = {}
    
    def __init__(self, id, name, dst, offset, current_offset):
        self.id = id
        self.name = name
        self.dst = dst
        self.offset = offset
        self.current_offset = current_offset

    @classmethod
    def createFromRaw(cls, data):
        timezone = RtmApiTimezone(data["id"], data["name"], data["dst"], data["offset"], data["current_offset"])
        return timezone
    
    @classmethod
    def createByZoneName(cls, timezoneName):
        if RtmApiTimezone.aTimezones:
            if timezoneName in RtmApiTimezone.aTimezones:
                return RtmApiTimezone.aTimezones[timezoneName]
            else:
                return None
        
    @classmethod
    def setTimezones(cls, aTimezones):
        RtmApiTimezone.aTimezones = {}
        for timezone in aTimezones:
            RtmApiTimezone.aTimezones[timezone.name] = timezone
    
    def gmtToUser(self, gmt):
        return gmt + int(self.offset)
    
    def __repr__(self):
        dstString = ""
        if self.dst == "1":
            dstString = "DST"
        return u"#%s %s %s offset: %s, current: %s" % (self.id, self.name, dstString, self.offset, self.current_offset)

class RtmApiSettings:
    def __init__(self, timezone, dateformat, timeformat, defaultlist, language):
        self.timezone = timezone
        self.dateformat = dateformat
        self.timeformat = timeformat
        self.defaultlist = defaultlist
        self.language = language
    
    @classmethod
    def createFromRaw(cls, data):
        settings = RtmApiSettings(data["timezone"], data["dateformat"], data["timeformat"], data["defaultlist"], data["language"])
        return settings

    def getTimezone(self):
        timezone = RtmApiTimezone.createByZoneName(self.timezone)
        if timezone == None:
            # not existing timezone is replaced with GMT
            return RtmApiTimezone(-1, "GMT", 0, 0, 0)
        else:
            return timezone
    
    def __repr__(self):
        return u"timezone:%s, dateformat:%s, timeformat: %s, defaultlist: %s, language: %s" % (self.timezone, self.dateformat, self.timeformat, self.defaultlist, self.language)
        
is_array = lambda var: isinstance(var, (list, tuple))


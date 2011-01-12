# coding: utf-8

import re
from RtmApi import RtmApi, RtmApiSettings, RtmApiTimezone
from RtmApi import RtmApiException
import logging
import TimezonesStorage
import time

class RtmBotUserError(Exception):
    pass

class RtmBot(object):
    def __init__(self, apiKey, apiSecret, adminJidHash, storage):
        self.adminJidHash = adminJidHash
        self.api = RtmApi(apiKey, apiSecret)
        self.__storage = storage
        
    def __fromStorage(self, name, default = None):
        if (self.__storage.exist(name)):
            return self.__storage.get(name)
        else:
            return default
    
    def processCommand(self, message):
        try:
            message = message.strip();
            
            if self.__fromStorage("frob") != None:
                # user has authenticated
                # obtain auth token
                
                frob = self.__fromStorage("frob")
                if frob != None:
                    try:
                        o = self.api.getToken(frob)
                        self.__storage.set("auth", o["token"])
                        self.__storage.delete("frob")
                        
                        return "Authenticated!\n\n" + self.getHelpMessage()
                    except RtmApiException, e:
                        self.__storage.delete("frob")
                        logging.exception(str(e))
                        return "Something went wrong. Please try to say something more"
                else:
                    return "No frob found. Please try to say something more"
            elif self.__fromStorage("auth") == None:
                # authentication
                
                frob = self.api.getFrob()
                self.__storage.set("frob", frob)
                return "Jabber2RTM\n\nFirst you need to grant access to RTM to me.\nPlease follow the URL: " + self.api.getDesktopAuthUrl(RtmApi.PERMS_DELETE, frob) + "\n\nThen say 'hey' to me"
            else:
                # check for commands
                
                self.api.setAuthToken(str(self.__storage.get("auth")))
                
                if message == "HELP":
                    self.__clearTaskContext();
                    
                    return self.getHelpMessage();
                
                elif message == "CONFIRMATION":
                    self.__clearTaskContext();
                    
                    return self.__commandConfirmation();
                elif re.search(ur"^(?:(?:L(?:IST)?)|\?)(\s+.+)?$", message):
                    aMatches = re.match(ur"^(?:(?:L(?:IST)?)|\?)(\s+.+)?$", message).groups()
                    if aMatches[0] != None:
                        query = aMatches[0].strip()
                    else:
                        query = ""
                    return self.__commandList(self.__createFilterString(query));
                else:
                    result = self.__parseCommandWithTaskId(message)
                    if result != None:
                        return result
                    elif message != "":
                        self.__clearTaskContext();
                        
                        # parse message as '<name>\n<note>'
                        if re.search(ur"^([^\n]+)\n(.+)$", message, re.DOTALL):
                            aMatches = re.match(ur"^([^\n]+)\n(.+)$", message, re.DOTALL).groups()
                            message = aMatches[0];
                            note    = aMatches[1];
                        else:
                            note = None
                        
                        return self.__commandAddTask(message, note);
                    else:
                        return ""
        except RtmBotUserError, e:
            return "ERROR: " + str(e)

    def __commandCompleteTask(self, listId, taskseriesId, taskId):
        self.api.taskComplete(listId, taskseriesId, taskId)
        
        if self.__fromStorage("confirmation", True):
            return "Task completed"

    def __commandDeleteTask(self, listId, taskseriesId, taskId):
        self.api.taskDelete(listId, taskseriesId, taskId)
        
        if self.__fromStorage("confirmation", True):
            return "Task deleted"
    
    def __afterCommandDeleteTask(self, contextId):
        self.__removeTaskFromContext(contextId)
        
    def __commandPostponeTask(self, listId, taskseriesId, taskId):
        self.api.taskPostpone(listId, taskseriesId, taskId)
        
        if self.__fromStorage("confirmation", True):
            return "Task postponed"
    
    def __commandAddTagsToTask(self, listId, taskseriesId, taskId, tags):
        (listIdToMove, tags) = self.__excludeLists(listId, taskseriesId, taskId, tags)
        
        if listIdToMove != None:
            list = self.api.taskMoveTo(listId, taskseriesId, taskId, listIdToMove)
            
            # update context as List ID has changed
            aTaskseries = list.getTaskseries()
            self.updateInfoForTaskInContext(listId, taskseriesId, taskId, aTaskseries[0])
        
        if tags != "":
            self.api.taskAddTags(listId, taskseriesId, taskId, tags)
        
        if self.__fromStorage("confirmation", True):
            return "Tags/List added"
    
    def __excludeLists(self, listId, taskseriesId, taskId, tags):
        aLists = self.api.listGetList()
        
        listIdToMove = None
        
        aListsLookup = {}
        for list in aLists:
            if not list.smart:
                aListsLookup[list.name.lower()] = list
        
        aNewTags = []
        aTags = re.split(ur"(?:(?:\s*,\s*)|\s+)", tags)
        for tag in aTags:
            tag = tag.lower()
            if tag in aListsLookup:
                if listId != aListsLookup[tag].id:
                    listIdToMove = aListsLookup[tag].id
            else:
                aNewTags.append(tag)
        
        tags = ",".join(aNewTags)
        
        return (listIdToMove, tags)
    
    def __commandRemoveTagsFromTask(self, listId, taskseriesId, taskId, tags):
        self.api.taskRemoveTags(listId, taskseriesId, taskId, tags)
        
        if self.__fromStorage("confirmation", True):
            return "Tags removed"
    
    def __commandList(self, filter):
        aLists = self.api.taskGetList(filter = filter)

        userSettings = self.__loadSettingsAndTimezones()        
        
        aList = []
        for list in aLists:
            aList.extend(list.getTaskseries())
            
        if len(aList) > 0:
            aList.sort(key = lambda element: element.task.due)
            
            self.__putTasksToContext(aList)
            
            i = 1;
            resultString = ""
            for item in aList:
                resultString += u"%i. %s\n\n" % (i, item.toString(userSettings))
                i += 1
                
            return resultString
        else:
            return "*no tasks*"

    def __loadSettingsAndTimezones(self):
        # load list of timezones
        RtmApiTimezone.setTimezones(TimezonesStorage.getTimezones(self.api))
        
        # load user settings from RTM or from cached in datastore value
        return self.__getUserSettings()
            
    def __getUserSettings(self):
        settingsRaw = self.__fromStorage("settings", None)
        lastUpdated = self.__fromStorage("settingsLastUpdated", None)

        # check if settings has expired        
        if lastUpdated != None and time.mktime(time.gmtime()) - lastUpdated > 3600:
            settingsRaw = None
            
        if settingsRaw == None:
            settings = self.api.settingsGetList()
            settingsRaw = {
                           "timezone": settings.timezone, 
                           "dateformat": settings.dateformat, 
                           "timeformat": settings.timeformat, 
                           "defaultlist": settings.defaultlist, 
                           "language": settings.language
                           }
            self.__storage.put("settings", settingsRaw)
            self.__storage.put("settingsLastUpdated", time.mktime(time.gmtime()))
            
        settings = RtmApiSettings(settingsRaw["timezone"], settingsRaw["dateformat"],
                                  settingsRaw["timeformat"], settingsRaw["defaultlist"], settingsRaw["language"])
        
        return settings
        
    def __commandConfirmation(self):
        if self.__fromStorage("confirmation", True):
            self.__storage.set("confirmation", False)
            return "Task add confirmation is now OFF"
        else:
            self.__storage.set("confirmation", True)
            return "Task add confirmation is now ON"
    
    def __commandAddTask(self, name, note):
        try:
            list = self.api.taskAdd(name, True)
            
            taskseries = list.getTaskseries()
            taskseries = taskseries[0]
            
            if (note != None):
                note = note.strip()
                
                aMatches = re.match(ur"^([^\n]+)\n(.+)$`", note, re.DOTALL)
                
                if aMatches != None and re.match(ur"http(s?)://", aMatches.groups()[0], re.IGNORECASE):
                    title = aMatches.groups()[0]
                    text = aMatches.groups()[1]
                else:
                    title = "Note"
                    text = note
                
                self.api.taskNoteAdd(title, text, list.id, taskseries.id, taskseries.task.id)
        except RtmApiException, e:
            logging.exception(e)
            return "ERROR: " . str(e)
        
        if self.__fromStorage("confirmation", True):
            userSettings = self.__loadSettingsAndTimezones()
            
            return "Task added: " + taskseries.toString(userSettings)
        
    def __putTasksToContext(self, aTaskseries):
        aNewContext = {}
        i = 1
        for taskseries in aTaskseries:
            aNewContext[str(i)] = (taskseries.listId, taskseries.id, taskseries.task.id)
            i += 1
        self.__storage.put("aContextTasks", aNewContext)
    
    def __getTaskFromContext(self, contextId):
#        try:
#            contextId = int(contextId)
#        except ValueError:
#            raise RtmBotUserError("Bad task ID: '%s'" % contextId)
        
        if not self.__storage.exist("aContextTasks"):
            self.__storage.set("aContextTasks", {})
        
        if contextId in self.__storage.get("aContextTasks"):
            return self.__storage.get("aContextTasks")[contextId]
        else:
            raise RtmBotUserError("There is no task with ID " + str(contextId) + " in your current context")
    
    def __removeTaskFromContext(self, contextId):
        if self.__storage.exist("aContextTasks"):
            context = self.__storage.get("aContextTasks")
            if context.has_key(contextId):
                del context[contextId]
                self.__storage.put("aContextTasks", context)
        
    def __clearTaskContext(self):
        self.__storage.set("aContextTasks", {})
        
    def __parseCommandWithTaskId(self, message):
        self.api.beginTimeline()
        
        aCommands = [
            {"method": self.__commandCompleteTask, "command": (u"C", u"COMPLETE", u"+", u"++")},
            {"method": self.__commandDeleteTask, "command": (u"D", u"DELETE", u"-")},
            {"method": self.__commandPostponeTask, "command": (u"P", u"POSTPONE", u">"), "context_callback": self.__afterCommandDeleteTask}, 
            {"method": self.__commandAddTagsToTask, "command": (u"T", u"TAGS", u"#"), "has_param": True},
            {"method": self.__commandRemoveTagsFromTask, "command": (u"-T", u"-TAGS", u"-#"), "has_param": True},
        ]
        
        for commandInfo in aCommands:
            method = commandInfo["method"]
            aliases = commandInfo["command"]
            moreParams = "has_param" in commandInfo and commandInfo["has_param"]
            
            rAliases = []
            for alias in aliases:
                rAliases.append(u"(?:" +  re.escape(alias) + ")")
            rAliases = u"|".join(rAliases)
            
            if moreParams:
                rMoreParams = ur"(\s+.+)"
            else:
                rMoreParams = u""

            # old '#123-456-789' task id notation
            aMatches = re.match(ur"^ (?: " + rAliases + ur") \s+ (?: \#? ) (\d+)-(\d+)-(\d+) " + rMoreParams + u" $", message, re.VERBOSE)
            
            if aMatches != None:
                aMatches = aMatches.groups()
                if moreParams:
                    return method(self, aMatches[0], aMatches[1], aMatches[2], aMatches[3].strip())
                else:
                    return method(self, aMatches[0], aMatches[1], aMatches[2])
            else:
                # 'id in the last list of tasks' task id notation
                aMatches = re.match(ur"^ (?: " + rAliases + ur" ) \s+ (\d+(?: \s* , \s* \d+)*) " + rMoreParams + u" $", message, re.VERBOSE)
                
                if aMatches != None:
                    aMatches = aMatches.groups()
                    
                    aIds = re.split(ur"\s*,\s*", aMatches[0])
                    
                    aResults = []
                    for id in aIds:
                        (listId, taskseriesId, taskId) = self.__getTaskFromContext(id)

                        if moreParams:
                            aResults.append(id + u" -- " + method(listId, taskseriesId, taskId, aMatches[1].strip()))
                        else:
                            aResults.append(id + u" -- " + method(listId, taskseriesId, taskId))
                            
                        if "context_callback" in commandInfo:
                            commandInfo["context_callback"](id)
                    
                    return "\n".join(aResults)

        return None
    
    def __answer(self, message):
        print message
        #print re.sub("\n", "<br>", cgi.escape(message, True)) + "<reset>"
                
    def __createFilterString(self, query):
        if query != "":
            if re.search(u":", query):
                # The query already has filters. Use it as is.
                filter = query
            else:
                # By default search by keywork, List, Tag or Location and only in incomplet tasks
                filter = u"(%(query)s OR list:%(query)s OR tag:%(query)s OR location:%(query)s) AND status:incomplete" % {"query": query}
            
            if not re.search("status:", query):
                # return only incomplete tasks if not specified explicitly
                filter += u" AND status:incomplete"
        else:
            filter = u"status:incomplete"
        
        return filter
    
    def getHelpMessage(self):
        return ur"""
:: Jabber2RTM Bot Commands List ::

HELP -- show this help message

LIST [filter] -- show the list of tasks with optional filter, see: http://www.rememberthemilk.com/help/answers/search/advanced.rtm
L [filter] -- LIST command alias
? [filter] -- LIST command alias

CONFIRMATION -- Turn On/Off showing command execution confirmation messages

:: About Task IDs ::

The commands below expect you to specify task ID. You can get task ID after you execute LIST command. The list is shown in the way:

ID1. <task name1>
ID2. <task name1>

ID1 and ID2 are task IDs for the corresponding task. You can use several IDs in one command, comma-separated.

:: Task Manipulation Commands ::

COMPLETE taskId -- mark the task as completed
C taskId -- COMPLETE command alias
+ taskId -- COMPLETE command alias

DELETE taskId -- delete the task
D taskId -- DELETE command alias
- taskId -- DELETE command alias

POSTPONE taskId -- Postpones a task. If the task has no due date or is overdue, its due date is set to today. Otherwise, the task due date is advanced a day.
P taskId -- POSTPONE command alias
> taskId -- POSTPONE command alias

TAGS taskId -- Add tags to the task or move the task to another list.
T taskId -- TAGS command alias
# taskId -- TAGS command alias

-TAGS taskId -- Remove tags from the task.
-T taskId -- -TAGS command alias
-# taskId -- -TAGS command alias

:: Adding New Task ::

If your message does not match the commands' formats specified above then it will be used to add a new task to RememberTheMilk.com using SmartAdd formatting method: http://www.rememberthemilk.com/services/smartadd/

Task format:
<task_name>
[<task_note>]

  * <task_name> -- the name of the task and optionally the SmartAdd data (tags, places, etc.)
  * <task_note> -- optional task note. Can be multiline.

:: News & Updates ::

  * Twitter: http://twitter.com/jabber2rtm
  * Juick: http://juick.com/jabber2rtm/

:: Source Code ::

The project is Open Souce so you can find souces (in PHP) here:

  * http://code.google.com/p/jabber2rtm/
"""

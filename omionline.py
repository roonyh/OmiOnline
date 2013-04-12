import webapp2
import random
import os
import json
import urllib
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.api import channel

class GameDetails():
    game_started = False
    game_waiting = False
    current_gamekey = None
    player_count = 0  

class OmiGame(db.Model):
    
    players = db.IntegerProperty
    user1 = db.UserProperty()
    user2 = db.UserProperty()
    user3 = db.UserProperty()
    user4 = db.UserProperty()
    trumpher = db.UserProperty()
    pack = db.StringListProperty()
    hand1 = db.StringListProperty()
    hand2 = db.StringListProperty()
    hand3 = db.StringListProperty()
    hand4 = db.StringListProperty()
    table = db.StringListProperty()
    starter = db.IntegerProperty()
    score = db.StringProperty()
    trump = db.StringProperty()
    date = db.DateTimeProperty(auto_now_add=True)
    rounds = db.IntegerProperty()
    
class MainHandler(webapp2.RequestHandler):

    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return
        
        q = OmiGame.all().order('-date')
        games = q.fetch(10)
        gameurls = zip(["%s's game" % game.user1 for game in games],map( (lambda g:'/join?'+urllib.urlencode({'g': g})), [str(g.user1.user_id()) for g in games]))
        url = users.create_logout_url(self.request.uri)
        template_values = {
                           'game_urls' :  gameurls,
                           'url': url
                          }
        path = os.path.join(os.path.dirname(__file__), 'index.html')

        self.response.out.write(template.render(path, template_values))
        

class GameConnector(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        game = OmiGame.get_by_key_name(self.request.get('g'))
        pid = 0
        if not game.user2:    
            game.user2 = user
            game.put()
            pid = 1 #0 base
            message ='Your are Player 2. '
        elif not game.user3:    
            game.user3 = user
            game.put()
            pid = 2
            message ='Your are Player 3. '
        elif not game.user4:    
            game.user4 = user
            game.put()
            pid = 3
            message ='Your are Player 4. ' 
        else:
            message = 'Game is full'
        token = channel.create_channel(user.user_id() + game.user1.user_id())
        url = users.create_logout_url(self.request.uri)
        template_values = {
                           'token' : token,
                           'message' : message,
                           'id' : pid,
                           'game_key' : str(game.user1.user_id()),
                           'url': url
                          }
        path = os.path.join(os.path.dirname(__file__), 'game.html')
        self.response.out.write(template.render(path, template_values))    
        
class GameCreator(webapp2.RequestHandler):            
    def post(self):
        user = users.get_current_user()
        game_key = user.user_id() #key of  each game is the creators id
        game = OmiGame(key_name = game_key)
        game.user1 = user
        game.starter = -1
        game.rounds = 0
        game.put()
        message = 'Your are Player 1. '
        token = channel.create_channel(user.user_id() + game.user1.user_id())
        url = users.create_logout_url(self.request.uri)
        template_values = {
                           'token' : token,
                           'message' : message,
                           'id' : 0,
                           'game_key' : game.user1.user_id(),
                           'url': url
                          }
        path = os.path.join(os.path.dirname(__file__), 'game.html')
        self.response.out.write(template.render(path, template_values))
        
class Responder(webapp2.RequestHandler):            
    def post(self):
        user = users.get_current_user()
        game = OmiGame.get_by_key_name(self.request.get('g'))
        if game.user1:
            channel.send_message(game.user1.user_id() + game.user1.user_id() , create_message('%s connected.' % user.nickname()))
        if game.user2:
            channel.send_message(game.user2.user_id() + game.user1.user_id() , create_message('%s connected.' % user.nickname()))  
        if game.user3:
            channel.send_message(game.user3.user_id() + game.user1.user_id() , create_message('%s connected.' % user.nickname()))  
        if game.user4:
            channel.send_message(game.user4.user_id() + game.user1.user_id() , create_message('%s connected.' % user.nickname())) 
            create_round(game)
            msg1,msg2,msg3,msg4 = create_init_msg(game) 
            channel.send_message(game.user1.user_id() + game.user1.user_id(),'%s' % msg1)
            channel.send_message(game.user2.user_id() + game.user1.user_id(),'%s' % msg2)
            channel.send_message(game.user3.user_id() + game.user1.user_id(),'%s' % msg3)
            channel.send_message(game.user4.user_id() + game.user1.user_id(),'%s' % msg4) 
            
class TrumpsSelector(webapp2.RequestHandler): 
    def post(self):
        game = OmiGame.get_by_key_name(self.request.get('g'))
        game.trump = self.request.get('t')
        game.put()
        create_full_hand(game)             
        msg1,msg2,msg3,msg4 = create_wholehand_msg(game) 
        channel.send_message(game.user1.user_id() + game.user1.user_id(),'%s' % msg1)
        channel.send_message(game.user2.user_id() + game.user1.user_id(),'%s' % msg2)
        channel.send_message(game.user3.user_id() + game.user1.user_id(),'%s' % msg3)
        channel.send_message(game.user4.user_id() + game.user1.user_id(),'%s' % msg4)
        inform_users()
        
class CardPlayer(webapp2.RequestHandler): 
    def post(self):
        game = OmiGame.get_by_key_name(self.request.get('g'))
        card = self.request.get('c')
        pid = self.request.get('i')
        table = game.table
        table.append(card)
        game.table = table
        game.put()
        msg = ""
        if len(table)==4:
            winner = pick_winner(table)
            game.table = []
            r = game.rounds
            r = r+1
            game.rounds = r
            game.put()
            msg = create_played_msg(card,4,int(pid),winner)
            channel.send_message(game.user1.user_id() + game.user1.user_id(),'%s' % create_message("%d number of rounds" % r))
            channel.send_message(game.user2.user_id() + game.user1.user_id(),'%s' % create_message("%d number of rounds" % r))
            channel.send_message(game.user3.user_id() + game.user1.user_id(),'%s' % create_message("%d number of rounds" % r))
            channel.send_message(game.user4.user_id() + game.user1.user_id(),'%s' % create_message("%d number of rounds" % r)) 
        else:
            msg = create_played_msg(card,len(table),int(pid),(int(pid)+1)%4)  
        channel.send_message(game.user1.user_id() + game.user1.user_id(),'%s' % msg)
        channel.send_message(game.user2.user_id() + game.user1.user_id(),'%s' % msg)
        channel.send_message(game.user3.user_id() + game.user1.user_id(),'%s' % msg)
        channel.send_message(game.user4.user_id() + game.user1.user_id(),'%s' % msg)        
        if game.rounds == 8:
            game.rounds = 0
            game.put()
            create_round(game)
            msg1,msg2,msg3,msg4 = create_init_msg(game) 
            channel.send_message(game.user1.user_id() + game.user1.user_id(),'%s' % msg1)
            channel.send_message(game.user2.user_id() + game.user1.user_id(),'%s' % msg2)
            channel.send_message(game.user3.user_id() + game.user1.user_id(),'%s' % msg3)
            channel.send_message(game.user4.user_id() + game.user1.user_id(),'%s' % msg4)

def inform_users():
    msgp1 = "Welcome! You are the 'Player 1'"
    msgp2 = "Welcome! You are the 'Player 2'"
    msgp3 = "Welcome! You are the 'Player 3'"
    msgp4 = "Welcome! You are the 'Player 4'"
    #channel.send_message(game.user1.user_id() + game.user1.user_id(),'%s' % create_message(msgp1))
    #channel.send_message(game.user2.user_id() + game.user1.user_id(),'%s' % create_message(msgp2))
    #channel.send_message(game.user3.user_id() + game.user1.user_id(),'%s' % create_message(msgp3))
    #channel.send_message(game.user4.user_id() + game.user1.user_id(),'%s' % create_message(msgp4))
            
def pick_winner(table):
    return 3
                        
def create_round(game):
    cards = ["%s_%s" %(i,j) for i in 'scdh' for j in '789tjqka' ]  
    random.shuffle(cards)
    game.pack = cards
    game.hand1 = cards[:4] 
    game.hand2 = cards[4:8] 
    game.hand3 = cards[8:12]
    game.hand4 = cards[12:16] 
    i = game.starter
    game.starter = (i+1)%4 #0 base user index to represent the starter of each round                    
    game.put()

def create_played_msg(card,num,now,next):
    message = {
        'type' : 'playedcard',
        'card': card,
        'num': num, #describes which card of the table out of 1,2,3,4
        'now':now,
        'next' : next,
        'mes' : 'Card played'
     }
    return json.dumps(message)
    
def create_full_hand(game):
    cards = game.pack
    h1 = game.hand1
    h1.extend(cards[16:20])
    game.hand1 = h1   
    h2 = game.hand2
    h2.extend(cards[20:24])
    game.hand2 = h2   
    h3 = game.hand3
    h3.extend(cards[24:28])
    game.hand3 = h3
    h4 = game.hand4
    h4.extend(cards[28:32])
    game.hand4 = h4                  
    game.put()    
    
def create_message(msg):   
    message = {
        'type':'message',
        'text':msg
    }
    return json.dumps(message)
    
def create_init_msg(game):
    gameUpdate = [{},{},{},{}]
    gameUpdate[0] = {
      'type': 'firstfour' , 
      'hand': game.hand1  
       
    }
    gameUpdate[1] = {
      'type': 'firstfour' , 
      'hand': game.hand2   
    }
    gameUpdate[2] = {
      'type': 'firstfour' , 
      'hand': game.hand3   
    }
    gameUpdate[3] = {
      'type': 'firstfour' , 
      'hand': game.hand4   
    }
    i = game.starter
    gu = gameUpdate[(i+1)%4] #find the player after the starter
    gu['trumps']='yes' #that player is the trumpher
    return json.dumps(gameUpdate[0]),json.dumps(gameUpdate[1]),json.dumps(gameUpdate[2]),json.dumps(gameUpdate[3])
    
def create_wholehand_msg(game):
    gameUpdate = [{},{},{},{},{},{},{},{}]
    gameUpdate[0] = {
      'type': 'wholehand' , 
      'hand': game.hand1 ,  
      'mes': "%s are selected as trumphs" % ("Spades" if game.trump == "s" else "Clubs" if game.trump == "c" else "Hearts" if  game.trump == "h" else "Diamonds")
    }
    gameUpdate[1] = {
      'type': 'wholehand' , 
      'hand': game.hand2 ,
      'mes': "%s are selected as trumphs" % ("Spades" if game.trump == "s" else "Clubs" if game.trump == "c" else "Hearts" if  game.trump == "h" else "Diamonds")
    }
    gameUpdate[2] = {
      'type': 'wholehand' , 
      'hand': game.hand3 ,  
      'mes': "%s are selected as trumphs" % ("Spades" if game.trump == "s" else "Clubs" if game.trump == "c" else "Hearts" if  game.trump == "h" else "Diamonds")
    }
    gameUpdate[3] = {
      'type': 'wholehand' , 
      'hand': game.hand4 , 
      'mes': "%s are selected as trumphs" % ("Spades" if game.trump == "s" else "Clubs" if game.trump == "c" else "Hearts" if  game.trump == "h" else "Diamonds")
    }
    i = game.starter
    gu = gameUpdate[(i+1)%4]
    gu['trumps']='yes'
    return json.dumps(gameUpdate[0]),json.dumps(gameUpdate[1]),json.dumps(gameUpdate[2]),json.dumps(gameUpdate[3])    
    
        
app = webapp2.WSGIApplication([('/', MainHandler),('/create', GameCreator),('/join', GameConnector),('/resp', Responder),('/tru',TrumpsSelector),('/plcrd',CardPlayer)], debug=True)



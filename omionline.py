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

    players = db.IntegerProperty()
    nickname = db.StringProperty()
    user1 = db.UserProperty()
    user2 = db.UserProperty()
    user3 = db.UserProperty()
    user4 = db.UserProperty()
    handwinner = db.IntegerProperty()
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



class Player(db.Model):
    game = db.ReferenceProperty(OmiGame)
    pid = db.IntegerProperty()

class MainHandler(webapp2.RequestHandler):

    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return

        q = OmiGame.all().order('-date')
        games = q.fetch(10)
        gameurls = zip(["%s's-game-%d-Player(s)" % (game.nickname,game.players) for game in games],map( (lambda g:'/join?'+urllib.urlencode({'g': g})), [str(g.user1.user_id()) for g in games]))
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
        if(user==game.user1 or user==game.user2 or user==game.user3 or user==game.user4):
            channel.send_message(user.user_id() + game.user1.user_id(), create_message("You are a player in this game"))
        else:
            if not game.user2:
                game.user2 = user
                game.players = 2
                game.put()
                pid = 1 #0 base'
            elif not game.user3:
                game.user3 = user
                game.players = 3
                game.put()
                pid = 2
            elif not game.user4:
                game.user4 = user
                game.players = 4
                game.put()
                pid = 3
            else:
               self.response.out.write("Game is full")
               return

        token = channel.create_channel(user.user_id() + game.user1.user_id())
        player = Player(key_name = user.user_id()+game.user1.user_id())
        player.game = game
        player.pid = pid
        player.put()
        
        
        url = users.create_logout_url(self.request.uri)
        template_values = {
                           'token' : token,
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
        game.score = "0 0 0 0"
        game.players = 1
        gamename = self.request.get("nickname", default_value="Somapala")
        game.nickname = gamename
        game.put()
        
        token = channel.create_channel(user.user_id() + game.user1.user_id())
        player = Player(key_name = user.user_id()+game.user1.user_id())
        player.game = game
        player.pid = 0
        player.put()
        
        url = users.create_logout_url(self.request.uri)
        template_values = {
                           'token' : token,
                           'id' : 0,
                           'game_key' : str(game.user1.user_id()),
                           'url': url
                          }
        path = os.path.join(os.path.dirname(__file__), 'game.html')
        self.response.out.write(template.render(path, template_values))
        

class Responder(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        game = OmiGame.get_by_key_name(self.request.get('g'))
        if game.user1:
            channel.send_message(game.user1.user_id() + game.user1.user_id() , create_message('%s joined.' % "Player 1"))
        if game.user2:
            channel.send_message(game.user2.user_id() + game.user1.user_id() , create_message('%s joined.' % "Player 2"))
        if game.user3:
            channel.send_message(game.user3.user_id() + game.user1.user_id() , create_message('%s joined.' % "Player 3"))
        if game.user4:
            channel.send_message(game.user4.user_id() + game.user1.user_id() , create_message('%s joined.' % "Player 4"))
            create_round(game)
            msg1,msg2,msg3,msg4 = create_init_msg(game)
            channel.send_message(game.user1.user_id() + game.user1.user_id(),'%s' % msg1)
            channel.send_message(game.user2.user_id() + game.user1.user_id(),'%s' % msg2)
            channel.send_message(game.user3.user_id() + game.user1.user_id(),'%s' % msg3)
            channel.send_message(game.user4.user_id() + game.user1.user_id(),'%s' % msg4)
            

class TrumpsSelector(webapp2.RequestHandler):
    def post(self):
        game = OmiGame.get_by_key_name(self.request.get('g'))
        if get_current_user_pid(game) != game.handwinner:
            channel.send_message(game.user1.user_id() + game.user1.user_id() , create_message('Not allowed'))
            return
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
            winner,score = pick_winner(table,game.trump,game.handwinner,game.score)
            game.handwinner = winner
            game.table = []
            r = game.rounds
            r = r+1
            game.rounds = r
            game.score = score
            game.put()
            msg1,msg2,msg3,msg4 = create_played_msg(card,4,int(pid),winner,score)
        else:
            msg1,msg2,msg3,msg4 = create_played_msg(card,len(table),int(pid),(int(pid)+1)%4,game.score)
        channel.send_message(game.user1.user_id() + game.user1.user_id(),'%s' % msg1)
        channel.send_message(game.user2.user_id() + game.user1.user_id(),'%s' % msg2)
        channel.send_message(game.user3.user_id() + game.user1.user_id(),'%s' % msg3)
        channel.send_message(game.user4.user_id() + game.user1.user_id(),'%s' % msg4)
        if game.rounds == 8:
            game.rounds = 0
            game.put()
            create_round(game)
            msg1,msg2,msg3,msg4 = create_init_msg(game)
            channel.send_message(game.user1.user_id() + game.user1.user_id(),'%s' % msg1)
            channel.send_message(game.user2.user_id() + game.user1.user_id(),'%s' % msg2)
            channel.send_message(game.user3.user_id() + game.user1.user_id(),'%s' % msg3)
            channel.send_message(game.user4.user_id() + game.user1.user_id(),'%s' % msg4)
            

class DisconnectHandler(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('from')
        plr = Player.get_by_key_name(client_id)
        game = plr.game
        msg = create_message("Player %d disconnected. <br>Sorry the game cannot continue :( Click Home" % (plr.pid+1))
        channel.send_message(game.user1.user_id() + game.user1.user_id(),'%s' % msg)
        channel.send_message(game.user2.user_id() + game.user1.user_id(),'%s' % msg)
        channel.send_message(game.user3.user_id() + game.user1.user_id(),'%s' % msg)
        channel.send_message(game.user4.user_id() + game.user1.user_id(),'%s' % msg)
        game.delete()

def inform_users():
    msgp1 = "Welcome! You are the 'Player 1'"
    msgp2 = "Welcome! You are the 'Player 2'"
    msgp3 = "Welcome! You are the 'Player 3'"
    msgp4 = "Welcome! You are the 'Player 4'"
    #channel.send_message(game.user1.user_id() + game.user1.user_id(),'%s' % create_message(msgp1))
    #channel.send_message(game.user2.user_id() + game.user1.user_id(),'%s' % create_message(msgp2))
    #channel.send_message(game.user3.user_id() + game.user1.user_id(),'%s' % create_message(msgp3))
    #channel.send_message(game.user4.user_id() + game.user1.user_id(),'%s' % create_message(msgp4))
    

def pick_winner(table,tru,handwinner,score):
    tot = 0
    wincard = 0
    i = -1
    first = table[0]
    fc = first[0]
    for c in table:
        i=i+1
        cardscore = 0;
        if c[0] == tru:
            cardscore=10+int(c[-1])
        if c[0] == fc:
            cardscore=int(c[-1])
        if cardscore>tot:
            tot=cardscore
            wincard=i

    plr = (handwinner+wincard) % 4 #zero based
    scores = score.split()
    scores[plr%2] = str(int(scores[plr%2])+1)
    scores = " ".join(scores)
    return plr,scores
    

def create_round(game):
    cards = ["%s_%s" %(i,j) for i in 'cdeh' for j in '12345678' ]
    random.shuffle(cards)
    game.pack = cards
    cards[:4].sort()
    game.hand1 = cards[:4]
    cards[4:8].sort()
    game.hand2 = cards[4:8]
    cards[8:12].sort()
    game.hand3 = cards[8:12]
    cards[12:16].sort()
    game.hand4 = cards[12:16]
    i = game.starter
    game.starter = (i+1)%4 #0 base user index to represent the starter of each round
    game.handwinner = (i+2)%4
    f,s,fr,sr = game.score.split()
    if int(f)>int(s):
        game.score = " ".join(["0","0",str(int(fr)+1),str(int(sr))])
    if int(f)<int(s):
        game.score = " ".join(["0","0",str(int(fr)),str(int(sr)+1)])
    if int(s)==int(f):
        game.score = " ".join(["0","0",str(int(fr)),str(int(sr))])
    game.put()
    

def create_played_msg(card,num,now,next,score):
    f,s,fr,sr= score.split()
    message = [{},{},{},{}]
    message[0] = {
        'type' : 'playedcard',
        'card': card,
        'num': num, #describes which card of the table out of 1,2,3,4
        'now':now,
        'next' : next,
        'y' : f,
        'o' : s,
        'yr' : fr,
        'or' : sr
    }
    message[1] = {
        'type' : 'playedcard',
        'card': card,
        'num': num, #describes which card of the table out of 1,2,3,4
        'now':now,
        'next' : next,
        'y' : s,
        'o' : f,
        'yr' : sr,
        'or' : fr
    }
    message[2] = {
        'type' : 'playedcard',
        'card': card,
        'num': num, #describes which card of the table out of 1,2,3,4
        'now':now,
        'next' : next,
        'y' : f,
        'o' : s,
        'yr' : fr,
        'or' : sr
    }
    message[3] = {
        'type' : 'playedcard',
        'card': card,
        'num': num, #describes which card of the table out of 1,2,3,4
        'now':now,
        'next' : next,
        'y' : s,
        'o' : f,
        'yr' : sr,
        'or' : fr
    }
    return json.dumps(message[0]),json.dumps(message[1]),json.dumps(message[2]),json.dumps(message[3]),
    

def create_full_hand(game):
    cards = game.pack
    h1 = game.hand1
    h1.extend(cards[16:20])
    h1.sort()
    game.hand1 = h1
    h2 = game.hand2
    h2.extend(cards[20:24])
    h2.sort()
    game.hand2 = h2
    h3 = game.hand3
    h3.extend(cards[24:28])
    h3.sort()
    game.hand3 = h3
    h4 = game.hand4
    h4.extend(cards[28:32])
    h4.sort()
    game.hand4 = h4
    game.put()
    

def create_message(msg,typ="message"):
    message = {
        'type':typ,
        'text':msg
    }
    return json.dumps(message)
    

def create_init_msg(game):
    gameUpdate = [{},{},{},{}]
    i = game.starter
    gameUpdate[0] = {
      'type': 'firstfour' ,
      'hand': game.hand1,
      'trumphs' : (i+1)%4
    }
    gameUpdate[1] = {
      'type': 'firstfour' ,
      'hand': game.hand2,
      'trumphs' : (i+1)%4
    }
    gameUpdate[2] = {
      'type': 'firstfour' ,
      'hand': game.hand3,
      'trumphs' : (i+1)%4
    }
    gameUpdate[3] = {
      'type': 'firstfour' ,
      'hand': game.hand4,
      'trumphs' : (i+1)%4
    }
    return json.dumps(gameUpdate[0]),json.dumps(gameUpdate[1]),json.dumps(gameUpdate[2]),json.dumps(gameUpdate[3])
    

def create_wholehand_msg(game):
    gameUpdate = [{},{},{},{},{},{},{},{}]
    gameUpdate[0] = {
      'type': 'wholehand' ,
      'hand': game.hand1 ,
      'mes': "%s" % ("Spades" if game.trump == "e" else "Clubs" if game.trump == "c" else "Hearts" if  game.trump == "h" else "Diamonds")
    }
    gameUpdate[1] = {
      'type': 'wholehand' ,
      'hand': game.hand2 ,
      'mes': "%s" % ("Spades" if game.trump == "e" else "Clubs" if game.trump == "c" else "Hearts" if  game.trump == "h" else "Diamonds")
    }
    gameUpdate[2] = {
      'type': 'wholehand' ,
      'hand': game.hand3 ,
      'mes': "%s" % ("Spades" if game.trump == "e" else "Clubs" if game.trump == "c" else "Hearts" if  game.trump == "h" else "Diamonds")
    }
    gameUpdate[3] = {
      'type': 'wholehand' ,
      'hand': game.hand4 ,
      'mes': "%s" % ("Spades" if game.trump == "e" else "Clubs" if game.trump == "c" else "Hearts" if  game.trump == "h" else "Diamonds")
    }
    i = game.starter
    gu = gameUpdate[(i+1)%4]
    gu['trumps']='yes'
    return json.dumps(gameUpdate[0]),json.dumps(gameUpdate[1]),json.dumps(gameUpdate[2]),json.dumps(gameUpdate[3])

def get_current_user_pid(game):
    user = users.get_current_user()
    if(user==game.user1):
        return 0;
    if(user==game.user2):
        return 1;
    if(user==game.user3):
        return 2;
    if(user==game.user4):
        return 3;
            
app = webapp2.WSGIApplication([('/', MainHandler),('/create', GameCreator),('/join', GameConnector),('/resp', Responder),('/tru',TrumpsSelector),('/plcrd',CardPlayer),('/_ah/channel/disconnected/',DisconnectHandler)], debug=True)



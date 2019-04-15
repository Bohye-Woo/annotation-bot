#!/usr/bin/env python3

import logging
from getpass import getpass
from argparse import ArgumentParser
import datetime
import pickle
import numpy as np

import slixmpp
import ssl, os, requests, urllib
from bs4 import BeautifulSoup

from urllib.parse import quote as urlquote, unquote as urlunquote

nickname_color = {}

# import the pickled object, serializing and de-serializing a Python object)
def save_obj(obj, name):
    with open(name + '.pkl', 'wb') as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)

def load_obj(name):
    with open(name + '.pkl', 'rb') as f:
        return pickle.load(f)

# make a numbered text
def make_numbered_text(input_text, output_html):
    if not os.path.exists(output_html):  # if output_html path does not exist

        text = open(input_text, 'r')  # open the txt file
        lines = text.readlines()  # to divide the text into lines in the form {{"This is line 1"},{"This is line 2"},...}
        x = 1

        with open(output_html, 'w') as new_html:  # open the output_html with writing only as new_html
            new_html.write('<html><head><link rel="stylesheet" href="style.css" type="text/css"/><meta charset="utf-8"/><link rel="stylesheet" type="text/css" media="screen" href="https://cdn.conversejs.org/4.2.0/css/converse.min.css"><script src="https://cdn.conversejs.org/4.2.0/dist/converse.min.js" charset="utf-8"></script></head><body>')
            for line in lines:  # for each line in the list of lines
                new_html.write(
                    '<div class="linenum" id="linenum-{}"><div class="leftcolumn" id="leftcolumn-{}"><div class="linenumber">{}</div><div class="sentence">{}</div></div></div>'.format(
                        x, x, x, line))
                x = x + 1
            new_html.write('</body><script>converse.initialize({bosh_service_url: "https://conversejs.org/http-bind/", show_controlbox_by_default: true});</script></html>')
            print('I wrote a file', output_html)


# Get color from nickname_color dictionary. If it does not exist, create a color and save it
def get_nickname_color(nickname):
    if nickname not in nickname_color:  # If nickname is not in dict
        color = list(np.random.choice(range(256), size=3))  # Generate random new color
        nickname_color[nickname] = color  # Save new color in dict
        save_obj(nickname_color, 'nickname_color')
    return nickname_color[nickname]


# (parameter variable,parameter variable,parameter variable)
def insert_comment_at_line(output_html, comment, line_number, nickname):
    with open(output_html, 'r') as f:
        text = f.read()
        html = BeautifulSoup(text, 'html.parser')

    div_id = 'linenum-{}'.format(line_number)  # out comes linenum-line_number
    line = html.find('div', {'id': div_id})  # find the div that has the id div_id (has the id linenum-line_number)

    if not html.find('div', {
        'id': 'rightcolumn-{}'.format(line_number)}):  # if there is no div with id rightcolumn-line_number
        # then make a new div with rightcolumn-line_number and class rightcolumn. Then, append it to the line variable.
        right_column = html.new_tag("div")
        right_column['id'] = 'rightcolumn-{}'.format(line_number)
        right_column['class'] = 'rightcolumn'
        line.append(right_column)
    else:
        right_column = html.find('div', {'id': 'rightcolumn-{}'.format(line_number)})

    time = datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")

    color = get_nickname_color(nickname)
    print(color)
    # new_comment = html.new_tag("comment")  # make <comment></comment>
    new_comment = html.new_tag("div")  # make <comment></comment>
    new_comment['id'] = 'comment-{}'.format(line_number)
    new_comment['class'] = 'comment'
    # new_comment['style'] = 'text-decoration: underline; -webkit-text-decoration-color: rgb(' + str(color[0]) + ',' + str(color[1]) + ',' + str(color[2])+');'
    
    comment_text = html.new_tag("span")
    comment_text['style'] = 'border-bottom: 2px solid rgb(' + str(color[0]) + ',' + str(color[1]) + ',' + str(color[2])+');'
    
    #remove #comment <number>
    comment = comment.split(' ',2)[2] 

    comment_text.string = nickname + ': ' + comment + ' (' + time + ') ' # make <comment>comment (the parameter variable)</comment>
    comment_text['class'] = 'comment-text'
    new_comment.append(comment_text)
    right_column.append(new_comment)

    print(line, comment, '#' + str(line_number) + '#')
    print(div_id)

    if line:
        with open(output_html, 'w') as f:
            right_column.append(new_comment)
            f.write(html.decode())


def insert_media_at_line(output_html, mediafile, line_number):
    with open(output_html, 'r') as f:
        text = f.read()
        html = BeautifulSoup(text, 'html.parser')

    div_id = 'linenum-{}'.format(line_number)
    line = html.find('div', {'id': div_id})

    if not html.find('div', {'id': 'rightcolumn-{}'.format(line_number)}):
        right_column = html.new_tag("div")
        right_column['id'] = 'rightcolumn-{}'.format(line_number)
        right_column['class'] = 'rightcolumn'
        line.append(right_column)
    else:
        right_column = html.find('div', {'id': 'rightcolumn-{}'.format(line_number)})

    print(line, mediafile, '#' + str(line_number) + '#')
    print(div_id)

    if line:
        # notes to self write function to the detect media type
        with open(output_html, 'w') as f:
            new_image = html.new_tag("img", src=mediafile)
            right_column.append(new_image)
            f.write(html.decode())


class MUCBot(slixmpp.ClientXMPP):
    def __init__(self, jid, password, room, nick, output):

        slixmpp.ClientXMPP.__init__(self, jid, password)

        self.room = room
        self.nick = nick
        self.output = output
        self.current_line = 0

        self.add_event_handler("session_start", self.start)  # moment that it logs on
        self.add_event_handler("groupchat_message", self.muc_message)  # moment that someone start speaking someone

        output = self.output
        if not os.path.exists(output):
            os.mkdir(output)

        make_numbered_text('text.txt', 'index.html')

    def start(self, event):

        self.get_roster()
        self.send_presence()

        # https://xmpp.org/extensions/xep-0045.html
        self.plugin['xep_0045'].join_muc(self.room,
                                         self.nick,
                                         # If a room password is needed, use:
                                         # password=the_room_password,
                                         wait=True)

    def muc_message(self, msg):

        # Always check that a message is not the bot itself, otherwise you will create an infinite loop responding to your own messages.
        if msg['mucnick'] != self.nick:

            # Check if an OOB URL is included in the stanza (which is how an image is sent)
            # (OOB object - https://xmpp.org/extensions/xep-0066.html#x-oob)
            if len(msg['oob']['url']) > 0:
                # UPLOADED IMAGE
                # Send a reply
                self.send_message(mto=msg['from'].bare,
                                  mbody="Really? Oke. I'll add your photo for you, {}.".format(msg['mucnick']),
                                  mtype='groupchat')

                # Save the image to the output folder
                url = msg['oob']['url']  # grep the url in the message
                # urlunquote is like url to filename
                filename = os.path.basename(urlunquote(url))  # grep the filename in the url
                output = self.output
                # if not os.path.exists(output):
                #   os.mkdir(output)
                output_path = os.path.join(output, filename)

                u = urllib.request.urlopen(url)  # read the image data
                new_html = open(output_path, 'wb')  # open the output file
                new_html.write(u.read())  # write image to file
                new_html.close()  # close the output file

                # If we haven't set current line yet, prompt the user to do so
                if self.current_line < 0:
                    self.send_message(mto=msg['from'].bare,
                                      mbody="{}, before uploading an image, please use the following syntax: #image <line number>".format(
                                          msg['mucnick']),
                                      mtype='groupchat')

                # Add image to stream
                img = output_path
                insert_media_at_line('index.html', img, self.current_line)

            else:
                # TEXT MESSAGE
                words = msg['body'].split()
                linenum = words[1]
                if msg['body'].startswith("#image"):
                    if (linenum.isdigit()):
                        self.current_line = int(words[1])
                        self.send_message(mto=msg['from'].bare,
                                          mbody="Please now upload the image to be inserted on line {}.".format(
                                              self.current_line),
                                          mtype='groupchat')
                    else:
                        self.current_line = -1
                        self.send_message(mto=msg['from'].bare,
                                          mbody="{}, please use the following syntax: #image <line number>".format(
                                              msg['mucnick']),
                                          mtype='groupchat')
                if msg['body'].startswith("#comment"):
                    print(linenum)
                    if (linenum.isdigit()):
                        self.send_message(mto=msg['from'].bare,
                                          mbody="Really? Oke. I'll add your comment that for you, {}.".format(
                                              msg['mucnick']),
                                          mtype='groupchat')
                        # output_html,comment,line_number,username
                        insert_comment_at_line('index.html', msg['body'], linenum, msg['mucnick'])
                    else:
                        self.send_message(mto=msg['from'].bare,
                                          mbody="{}, please use the following syntax: #comment <line number> <message>...".format(
                                              msg['mucnick']),
                                          mtype='groupchat')


if __name__ == '__main__':
    # Setup the command line arguments.
    parser = ArgumentParser()  # making your own command line - ArgumentParser.

    # output verbosity options.
    parser.add_argument("-q", "--quiet", help="set logging to ERROR",
                        action="store_const", dest="loglevel",
                        const=logging.ERROR, default=logging.INFO)
    parser.add_argument("-d", "--debug", help="set logging to DEBUG",
                        action="store_const", dest="loglevel",
                        const=logging.DEBUG, default=logging.INFO)

    # JID and password options.
    parser.add_argument("-j", "--jid", dest="jid",  # jid = user
                        help="JID to use")
    parser.add_argument("-p", "--password", dest="password",
                        help="password to use")
    parser.add_argument("-r", "--room", dest="room",
                        help="MUC room to join")
    parser.add_argument("-n", "--nick", dest="nick",
                        help="MUC nickname")  # MUC = multi user chat

    # output folder for images
    parser.add_argument("-o", "--output", dest="output",
                        help="output folder, this is where the files are stored",
                        default="./output/", type=str)

    args = parser.parse_args()

    # Setup logging.
    logging.basicConfig(level=args.loglevel,
                        format='%(levelname)-8s %(message)s')

    if args.jid is None:
        args.jid = input("User: ")
    if args.password is None:
        args.password = getpass("Password: ")
    if args.room is None:
        args.room = input("MUC room: ")
    if args.nick is None:
        args.nick = input("MUC nickname: ")
    if args.output is None:
        args.output = input("Output folder: ")

    # Setup the MUCBot and register plugins. Note that while plugins may
    # have interdependencies, the order in which you register them does
    # not matter.
    xmpp = MUCBot(args.jid, args.password, args.room, args.nick, args.output)
    xmpp.register_plugin('xep_0030')  # Service Discovery
    xmpp.register_plugin('xep_0045')  # Multi-User Chat
    xmpp.register_plugin('xep_0199')  # XMPP Ping
    xmpp.register_plugin('xep_0066')  # Process URI's (files, images)

    # Connect to the XMPP server and start processing XMPP stanzas.
    xmpp.connect()
    xmpp.process()

    # Load color data
    if os.path.exists("nickname_color.pkl"):
        nickname_color = load_obj("nickname_color")  # Load dictionary from file into variable (nickname_color)

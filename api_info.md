Protocol
========

Pokémon Showdown's protocol is relatively simple.

Pokémon Showdown is implemented in SockJS. SockJS is a compatibility
layer over raw WebSocket, so you can actually connect to Pokémon
Showdown directly using WebSocket:

    ws://sim.smogon.com:8000/showdown/websocket
      or
    wss://sim3.psim.us/showdown/websocket

Client implementations you might want to look at for reference include:

- Majeur's android client (Kotlin/Java) -
    https://github.com/MajeurAndroid/Android-Unofficial-Showdown-Client
- pickdenis' chat bot (Ruby) -
    https://github.com/pickdenis/ps-chatbot
- Quinella and TalkTakesTime's chat bot (Node.js) -
    https://github.com/TalkTakesTime/Pokemon-Showdown-Bot
- Nixola's chat bot (Lua) -
    https://github.com/Nixola/NixPSbot
- Morfent's chat bot (Perl 6) -
    https://github.com/Kaiepi/p6-PSBot
- the official client (HTML5 + JavaScript) -
    https://github.com/smogon/pokemon-showdown-client

The official client logs protocol messages in the JavaScript console,
so opening that (F12 in most browsers) can help tell you what's going
on.


Client-to-server messages
-------------------------

Messages from the user to the server are in the form:

    ROOMID|TEXT

`ROOMID` can optionally be left blank if unneeded (commands like `/join lobby`
can be sent anywhere). Responses will be sent to a PM box with no username
(so `|/command` is equivalent to `|/pm ~, /command`).

`TEXT` can contain newlines, in which case it'll be treated the same
way as if each line were sent to the room separately.

A partial list of available commands can be found with `/help`.

To log in, look at the documentation for the `|challstr|` server message.


Server-to-client messages
-------------------------

Messages from the server to the user are in the form:

    >ROOMID
    MESSAGE
    MESSAGE
    MESSAGE
    ...

`>ROOMID` and the newline after it can be omitted if the room is lobby
or global. `MESSAGE` cannot start with `>`, so it's unambiguous whether
or not `>ROOMID` has been omitted.

As for the payload: it's made of any number of blocks of data
separated by newlines; empty lines should be ignored. In particular,
it should be treated the same way whether or not it ends in a
newline, and if the payload is empty, the entire message should be ignored.

If `MESSAGE` doesn't start with `|`, it should be shown directly in the
room's log. Otherwise, it will be in the form:

    |TYPE|DATA

For example:

    |j| Some dude
    |c|@Moderator|hi!
    |c| Some dude|you suck and i hate you!
    Some dude was banned by Moderator.
    |l| Some dude
    |b|battle-ou-12| Cool guy|@Moderator

This might be displayed as:

    Some dude joined.
    @Moderator: hi!
    Some dude: you suck and i hate you!
    Some dude was banned by Moderator.
    Some dude left.
    OU battle started between Cool guy and Moderator

For bandwidth reasons, five of the message types - `chat`, `join`, `leave`,
`name`, and `battle` - are sometimes abbreviated to `c`, `j`, `l`, `n`,
and `b` respectively. All other message types are written out in full so they
should be easy to understand.

Four of these can be uppercase: `J`, `L`, `N`, and `B`, which are
the equivalent of their lowercase versions, but are recommended not to be
displayed inline because they happen too often. For instance, the main server
gets around 5 joins/leaves a second, and showing that inline with chat would
make it near-impossible to chat.


Server-to-client message types
------------------------------

`USER` = a user, the first character being their rank (users with no rank are
represented by a space), and the rest of the string being their username.

### Room initialization

`|init|ROOMTYPE`

> The first message received from a room when you join it. `ROOMTYPE` is
> one of: `chat` or `battle`

`|title|TITLE`

> `TITLE` is the title of the room. The title is _not_ guaranteed to resemble
> the room ID; for instance, room `battle-gen7uu-779767714` could have title
> `Alice vs. Bob`.

`|users|USERLIST`

> `USERLIST` is a comma-separated list of `USER`s, sent from chat rooms when
> they're joined. Optionally, a `USER` can end in `@` followed by a user status message.
> A `STATUS` starting in `!` indicates the user is away.

### Room messages

`||MESSAGE` or `MESSAGE`

> We received a message `MESSAGE`, which should be displayed directly in
> the room's log.

`|html|HTML`

> We received an HTML message, which should be sanitized and displayed
> directly in the room's log.

`|uhtml|NAME|HTML`

> We recieved an HTML message (NAME) that can change what it's displaying,
> this is used in things like our Polls system, for example.

`|uhtmlchange|NAME|HTML`

> Changes the HTML display of the `|uhtml|` message named (NAME).

`|join|USER`, `|j|USER`, or `|J|USER`

> `USER` joined the room. Optionally, `USER` may be appended with `@!` to
> indicate that the user is away or busy.

`|leave|USER`, `|l|USER`, or `|L|USER`

> `USER` left the room.

`|name|USER|OLDID`, `|n|USER|OLDID`, or `|N|USER|OLDID`

> A user changed name to `USER`, and their previous userid was `OLDID`.
> Optionally, `USER` may be appended with `@!` to indicate that the user is
> away or busy.

`|chat|USER|MESSAGE` or `|c|USER|MESSAGE`

> `USER` said `MESSAGE`. Note that `MESSAGE` can contain `|` characters,
> so you can't just split by `|` and take the fourth string.
>
> If `MESSAGE` starts with `/`, it is a special message. For instance,
> `/me TEXT` or `/announce TEXT` or `/uhtml HTML`. A lot of these message
> types are abused to embed protocol messages in PMs (for instance, `/uhtml`
> is a stopgap before the client is rewritten to support `|uhtml|` etc in
> PMs).
>
> If the server wants clients to actually render a message starting with
> `/`, it will send a message starting with `//` (exactly like how users
> need to send those messages).

`|notify|TITLE|MESSAGE`

> Send a notification with `TITLE` and `MESSAGE` (usually, `TITLE` will be
> bold, and `MESSAGE` is optional).

`|notify|TITLE|MESSAGE|HIGHLIGHTTOKEN`

> Send a notification as above, but only if the user would be notified
> by a chat message containing `HIGHLIGHTTOKEN` (i.e. if `HIGHLIGHTTOKEN`
> contains words added to `/highlight`, or their username by default.)

`|:|TIMESTAMP`

`|c:|TIMESTAMP|USER|MESSAGE`

> `c:` is pretty much the same as `c`, but also comes with a UNIX timestamp;
> (the number of seconds since 1970). This is used for accurate timestamps
> in chat logs.
>
> `:` is the current time according to the server, so that times can be
> adjusted and reported in the local time in the case of a discrepancy.
>
> The exact fate of this command is uncertain - it may or may not be
> replaced with a more generalized way to transmit timestamps at some point.

`|battle|ROOMID|USER1|USER2` or `|b|ROOMID|USER1|USER2`

> A battle started between `USER1` and `USER2`, and the battle room has
> ID `ROOMID`.

### Global messages

`|popup|MESSAGE`

> Show the user a popup containing `MESSAGE`. `||` denotes a newline in
> the popup.

`|pm|SENDER|RECEIVER|MESSAGE`

> A PM was sent from `SENDER` to `RECEIVER` containing the message
> `MESSAGE`.

`|usercount|USERCOUNT`

> `USERCOUNT` is the number of users on the server.

`|nametaken|USERNAME|MESSAGE`

> You tried to change your username to `USERNAME` but it failed for the
> reason described in `MESSAGE`.

`|challstr|CHALLSTR`

> You just connected to the server, and we're giving you some information you'll need to log in.
>
> If you're already logged in and have session cookies, you can make an HTTP GET request to
> `https://play.pokemonshowdown.com/api/upkeep?challstr=CHALLSTR`
>
> Otherwise, you'll need to make an HTTP POST request to `https://play.pokemonshowdown.com/api/login`
> with the data `name=USERNAME&pass=PASSWORD&challstr=CHALLSTR`
>
> `USERNAME` is your username and `PASSWORD` is your password, and `CHALLSTR`
> is the value you got from `|challstr|`. Note that `CHALLSTR` contains `|`
> characters. (Also feel free to make the request to `https://` if your client
> supports it.)
>
> Either way, the response will start with `]` and be followed by a JSON
> object which we'll call `data`.
>
> Finish logging in (or renaming) by sending: `/trn USERNAME,0,ASSERTION`
> where `USERNAME` is your desired username and `ASSERTION` is `data.assertion`.

`|updateuser|USER|NAMED|AVATAR|SETTINGS`

> Your name, avatar or settings were successfully changed. Your rank and
> username are now `USER`. Optionally, `USER` may be appended with `@!` to
> indicate that you are away or busy.`NAMED` will be `0` if you are a guest
> or `1` otherwise. Your avatar is now `AVATAR`. `SETTINGS` is a JSON object
> representing the current state of various user settings.

`|formats|FORMATSLIST`

> This server supports the formats specified in `FORMATSLIST`. `FORMATSLIST`
> is a `|`-separated list of `FORMAT`s. `FORMAT` is a format name with one or
> more of these suffixes: `,#` if the format uses random teams, `,,` if the
> format is only available for searching, and `,` if the format is only
> available for challenging.
> Sections are separated by two vertical bars with the number of the column of
> that section prefixed by `,` in it. After that follows the name of the
> section and another vertical bar.

`|updatesearch|JSON`

> `JSON` is a JSON object representing the current state of what battles the
> user is currently searching for.

`|updatechallenges|JSON`

> `JSON` is a JSON object representing the current state of who the user
> is challenging and who is challenging the user.

`|queryresponse|QUERYTYPE|JSON`

> `JSON` is a JSON object representing containing the data that was requested
> with `/query QUERYTYPE` or `/query QUERYTYPE DETAILS`.
>
> Possible queries include `/query roomlist` and `/query userdetails USERNAME`.

### Tournament messages

`|tournament|create|FORMAT|GENERATOR|PLAYERCAP`

> `FORMAT` is the name of the format in which each battle will be played.
> `GENERATOR` is either `Elimination` or `Round Robin` and describes the
> type of bracket that will be used. `Elimination` includes a prefix
> that denotes the number of times a player can lose before being
> eliminated (`Single`, `Double`, etc.). `Round Robin` includes the
> prefix `Double` if every matchup will battle twice.
> `PLAYERCAP` is a number representing the maximum amount of players
> that can join the tournament or `0` if no cap was specified.

`|tournament|update|JSON`

> `JSON` is a JSON object representing the changes in the tournament
> since the last update you recieved or the start of the tournament.
> These include:
>
    format: the tournament's custom name or the format being used
    teambuilderFormat: the format being used; sent if a custom name was set
    isStarted: whether or not the tournament has started
    isJoined: whether or not you have joined the tournament
    generator: the type of bracket being used by the tournament
    playerCap: the player cap that was set or 0 if it was removed
    bracketData: an object representing the current state of the bracket
    challenges: a list of opponents that you can currently challenge
    challengeBys: a list of opponents that can currently challenge you
    challenged: the name of the opponent that has challenged you
    challenging: the name of the opponent that you are challenging

`|tournament|updateEnd`

> Signals the end of an update period.

`|tournament|error|ERROR`

> An error of type `ERROR` occurred.

`|tournament|forceend`

> The tournament was forcibly ended.

`|tournament|join|USER`

> `USER` joined the tournament.

`|tournament|leave|USER`

> `USER` left the tournament.

`|tournament|replace|OLD|NEW`

> The player `OLD` has been replaced with `NEW`

`|tournament|start|NUMPLAYERS`

> The tournament started with `NUMPLAYERS` participants.

`|tournament|replace|USER1|USER2`

> `USER1` was replaced by `USER2`.

`|tournament|disqualify|USER`

> `USER` was disqualified from the tournament.

`|tournament|battlestart|USER1|USER2|ROOMID`

> A tournament battle started between `USER1` and `USER2`, and the battle room
> has ID `ROOMID`.

`|tournament|battleend|USER1|USER2|RESULT|SCORE|RECORDED|ROOMID`

> The tournament battle between `USER1` and `USER2` in the battle room `ROOMID` ended.
> `RESULT` describes the outcome of the battle from `USER1`'s perspective
> (`win`, `loss`, or `draw`). `SCORE` is an array of length 2 that denotes the
> number of Pokemon `USER1` had left and the number of Pokemon `USER2` had left.
> `RECORDED` will be `fail` if the battle ended in a draw and the bracket type does
> not support draws. Otherwise, it will be `success`.

`|tournament|end|JSON`

> The tournament ended. `JSON` is a JSON object containing:
>
    results: the name(s) of the winner(s) of the tournament
    format: the tournament's custom name or the format that was used
    generator: the type of bracket that was used by the tournament
    bracketData: an object representing the final state of the bracket

`|tournament|scouting|SETTING`

> Players are now either allowed or not allowed to join other tournament
> battles based on `SETTING` (`allow` or `disallow`).

`|tournament|autostart|on|TIMEOUT`

> A timer was set for the tournament to auto-start in `TIMEOUT` seconds.

`|tournament|autostart|off`

> The timer for the tournament to auto-start was turned off.

`|tournament|autodq|on|TIMEOUT`

> A timer was set for the tournament to auto-disqualify inactive players
> every `TIMEOUT` seconds.

`|tournament|autodq|off`

> The timer for the tournament to auto-disqualify inactive players was
> turned off.

`|tournament|autodq|target|TIME`

> You have `TIME` seconds to make or accept a challenge, or else you will be
> disqualified for inactivity.


Battles
-------

### Playing battles

Battle rooms will have a mix of room messages and battle messages. [Battle
messages are documented in `SIM-PROTOCOL.md`][sim-protocol].

  [sim-protocol]: ./sim/SIM-PROTOCOL.md

To make decisions in battle, players should use the `/choose` command,
[also documented in `SIM-PROTOCOL.md`][sending-decisions].

  [sending-decisions]: ./sim/SIM-PROTOCOL.md#sending-decisions

### Starting battles through challenges

`|updatechallenges|JSON`

> `JSON` is a JSON object representing the current state of who the user
> is challenging and who is challenging the user. You'll get this whenever
> challenges update (when you challenge someone, when you receive a challenge,
> when you or someone you challenged accepts/rejects/cancels a challenge).

`JSON.challengesFrom` will be a `{userid: format}` table of received
challenges.

`JSON.challengeTo` will be a challenge if you're challenging someone, or `null`
if you haven't.

If you are challenging someone, `challengeTo` will be in the format:
`{"to":"player1","format":"gen7randombattle"}`.

To challenge someone, send:

    /utm TEAM
    /challenge USERNAME, FORMAT

To cancel a challenge you made to someone, send:

    /cancelchallenge USERNAME

To reject a challenge you received from someone, send:

    /reject USERNAME

To accept a challenge you received from someone, send:

    /utm TEAM
    /accept USERNAME

Teams are in [packed format](./sim/TEAMS.md#packed-format). `TEAM` can also be
`null`, if the format doesn't require user-built teams, such as Random Battle.

Invalid teams will send a `|popup|` with validation errors, and the `/accept`
or `/challenge` command won't take effect.

If the challenge is accepted, you will receive a room initialization message.

### Starting battles through laddering

`|updatesearch|JSON`

> `JSON` is a JSON object representing the current state of what battles the
> user is currently searching for. You'll get this whenever searches update
> (when you search, cancel a search, or you start or end a battle)

`JSON.searching` will be an array of format IDs you're currently searching for
games in.

`JSON.games` will be a `{roomid: title}` table of games you're currently in.
Note that this includes ALL games, so `|updatesearch|` will be sent when you
start/end challenge battles, and even non-Pokémon games like Mafia.

To search for a battle against a random opponent, send:

    /utm TEAM
    /search FORMAT

Teams are in packed format (see "Team format" below). `TEAM` can also be
`null`, if the format doesn't require user-built teams, such as Random Battle.

To cancel searching, send
    /cancelsearch

### Team format

Pokémon Showdown always sends teams over the protocol in packed format. For
details about how to convert and read this format, see [sim/TEAMS.md](./sim/TEAMS.md).

If you're not using JavaScript and don't want to reimplement these conversions,
[Pokémon Showdown's command-line client](./COMMANDLINE.md) can convert between
packed teams and JSON using standard IO.



Simulator protocol
==================

Pokémon Showdown's simulator protocol is implemented as a newline-and-pipe-delimited text stream. For details on how to read to or write from the text stream, see [sim/SIMULATOR.md](./SIMULATOR.md).


Receiving messages
------------------

### Battle initialization

The beginning of a battle will look something like this:

    |player|p1|Anonycat|60|1200
    |player|p2|Anonybird|113|1300
    |teamsize|p1|4
    |teamsize|p2|5
    |gametype|doubles
    |gen|7
    |tier|[Gen 7] Doubles Ubers
    |rule|Species Clause: Limit one of each Pokémon
    |rule|OHKO Clause: OHKO moves are banned
    |rule|Moody Clause: Moody is banned
    |rule|Evasion Abilities Clause: Evasion abilities are banned
    |rule|Evasion Moves Clause: Evasion moves are banned
    |rule|Endless Battle Clause: Forcing endless battles is banned
    |rule|HP Percentage Mod: HP is shown in percentages
    |clearpoke
    |poke|p1|Pikachu, L59, F|item
    |poke|p1|Kecleon, M|item
    |poke|p1|Jynx, F|item
    |poke|p1|Mewtwo|item
    |poke|p2|Hoopa-Unbound|
    |poke|p2|Smeargle, L1, F|item
    |poke|p2|Forretress, L31, F|
    |poke|p2|Groudon, L60|item
    |poke|p2|Feebas, L1, M|
    |teampreview
    |
    |start

`|player|PLAYER|USERNAME|AVATAR|RATING`

> Player details.
>
> - `PLAYER` is `p1` or `p2`
> - `PLAYER` may also be `p3` or `p4` in 4 player battles
> - `USERNAME` is the username
> - `AVATAR` is the player's avatar identifier (usually a number, but other
>    values can be used for custom avatars)
> - `RATING` is the player's Elo rating in the format they're playing. This will only be displayed in rated battles and when the player is first introduced otherwise it's blank

`|teamsize|PLAYER|NUMBER`

> - `PLAYER` is `p1`, `p2`, `p3`, or `p4`
> - `NUMBER` is the number of Pokémon your opponent starts with. In games
>   without Team Preview, you don't know which Pokémon your opponent has, but
>   you at least know how many there are.

`|gametype|GAMETYPE`

> - `GAMETYPE` is `singles`, `doubles`, `triples`, `multi`, or `freeforall`.

`|gen|GENNUM`

> Generation number, from 1 to 9. Stadium counts as its respective gens;
> Let's Go counts as 7, and modded formats count as whatever gen they were
> based on.

`|tier|FORMATNAME`

> The name of the format being played.

`|rated`

> Will be sent if the game will affect the player's ladder rating (Elo
> score).

`|rated|MESSAGE`

> Will be sent if the game is official in some other way, such as being
> a tournament game. Does not actually mean the game is rated.

`|rule|RULE: DESCRIPTION`

> Will appear multiple times, one for each 

    |clearpoke
    |poke|PLAYER|DETAILS|ITEM
    |poke|PLAYER|DETAILS|ITEM
    ...
    |teampreview

> These messages appear if you're playing a format that uses team previews.

`|clearpoke`

> Marks the start of Team Preview

`|poke|PLAYER|DETAILS|ITEM`

> Declares a Pokémon for Team Preview.
>
> - `PLAYER` is the player ID (see `|player|`)
> - `DETAILS` describes the pokemon (see "Identifying Pokémon" below)
> - `ITEM` will be `item` if the Pokémon is holding an item, or blank if it isn't.
>
> Note that forme and shininess are hidden on this, unlike on the `|switch|`
> details message.

`|start`

> Indicates that the game has started.

### Battle progress

`|`

> Clears the message-bar, and add a spacer to the battle history. This is
> usually done automatically by detecting the message-type, but can also
> be forced to happen with this.

`|request|REQUEST`

> Gives a JSON object containing a request for a choice (to move or
> switch). To assist in your decision, `REQUEST.active` has information
> about your active Pokémon, and `REQUEST.side` has information about your
> your team as a whole. `REQUEST.rqid` is an optional request ID (see
> "Sending decisions" for details).

`|inactive|MESSAGE` or `|inactiveoff|MESSAGE`

> A message related to the battle timer has been sent. The official client
> displays these messages in red.
>
> `inactive` means that the timer is on at the time the message was sent,
> while `inactiveoff` means that the timer is off.

`|upkeep`

> Signals the upkeep phase of the turn where the number of turns left for field
> conditions are updated.

`|turn|NUMBER`

> It is now turn `NUMBER`.

`|win|USER`

> `USER` has won the battle.

`|tie`

> The battle has ended in a tie.

`|t:|TIMESTAMP`

> The current UNIX timestamp (the number of seconds since 1970) - useful for determining
> when events occured in real time.

### Identifying Pokémon

Pokémon will be identified by a Pokémon ID (generally labeled `POKEMON` in
this document), and, in certain cases, also a details string (generally
labeled `DETAILS`).

A Pokémon ID is in the form `POSITION: NAME`.

- `POSITION` is the spot that the Pokémon is in: it consists of the `PLAYER`
  of the player (see `|player|`), followed by a position letter (`a` in
  singles).

An inactive Pokémon will not have a position letter.

In doubles and triples battles, `a` will refer to the leftmost Pokémon
from its trainer's perspective (so the leftmost on your team, and the
rightmost on your opponent's team, so `p1a` faces `p2c`, etc).

So the layout looks like:

Doubles, player 1's perspective:

    p2b p2a
    p1a p1b

Doubles, player 2's perspective:

    p1b p1a
    p2a p2b

In multi and free-for-all battles, players are grouped by parity. That is,
`p1` and `p3` share a side, as do `p2` and `p4`. The position letters still
follow the same conventions as in double battles, so the layout looks like:

Multi, player 1's perspective

    p4b p2a
    p1a p3b

- `NAME` is the nickname of the Pokémon (or the species name, if no nickname
  is given).

For example: `p1a: Sparky` could be a Charizard named Sparky.
`p1: Dragonite` could be an inactive Dragonite being healed by Heal Bell.

- `DETAILS` is a comma-separated list of all information about a Pokemon
  visible on the battle screen: species, shininess, gender, and level. So it
  starts with `SPECIES`, adding `, L##` if it's not level 100, `M` if it's male,
  `, F` if it's female, `, shiny` if it's shiny.
  In Gen 9, `, tera:TYPE` will be appended if the Pokemon has Terastallized.

So, for instance, `Deoxys-Speed` is a level 100 non-shiny genderless
Deoxys (Speed forme). `Sawsbuck, L50, F, shiny` is a level 50 shiny female
Sawsbuck (Spring form).

In Team Preview, `DETAILS` will not include information not available in
Team Preview (in particular, level and shininess will be left off), and
for Pokémon whose forme isn't revealed in Team Preview, it will be given as
`-*`. So, for instance, an Arceus in Team Preview would have the details
string `Arceus-*`, no matter what kind of Arceus it is.

For most commands, you can just use the position information in the
Pokémon ID to identify the Pokémon. Only a few commands actually change the
Pokémon in that position (`|switch|` switching, `|replace|` illusion dropping,
`|drag|` phazing, and `|detailschange|` permanent forme changes), and these
all specify `DETAILS` for you to perform updates with.

### Major actions

In battle, most Pokémon actions come in the form `|ACTION|POKEMON|DETAILS`
followed by a few messages detailing what happens after the action occurs.

Battle actions (especially minor actions) often come with tags such as
`|[from] EFFECT|[of] SOURCE`. `EFFECT` will be an effect (move, ability,
item, status, etc), and `SOURCE` will be a Pokémon. These can affect the
message or animation displayed, but do not affect anything else. Other 
tags include `|[still]` (suppress animation) and `|[silent]` (suppress
message).

`|move|POKEMON|MOVE|TARGET`

> The specified Pokémon has used move `MOVE` at `TARGET`. If a move has
> multiple targets or no target, `TARGET` should be ignored. If a move
> targets a side, `TARGET` will be a (possibly fainted) Pokémon on that
> side.
>
> If `|[miss]` is present, the move missed.
>
> If `|[still]` is present, the move should not animate 
>
> `|[anim] MOVE2` tells the client to use the animation of `MOVE2` instead
> of `MOVE` when displaying to the client.

`|switch|POKEMON|DETAILS|HP STATUS` or `|drag|POKEMON|DETAILS|HP STATUS`

> A Pokémon identified by `POKEMON` has switched in (if there was an old
> Pokémon in that position, it is switched out).
>
> For the DETAILS format, see "Identifying Pokémon" above.
>
> `POKEMON|DETAILS` represents all the information that can be used to tell
> Pokémon apart. If two pokemon have the same `POKEMON|DETAILS` (which will
> never happen in any format with Species Clause), you usually won't be able
> to tell if the same pokemon switched in or a different pokemon switched
> in.
>
> The switched Pokémon has HP `HP`, and status `STATUS`. `HP` is specified as
> a fraction; if it is your own Pokémon then it will be `CURRENT/MAX`, if not,
> it will be `/100` if HP Percentage Mod is in effect and `/48` otherwise.
> `STATUS` can be left blank, or it can be `slp`, `par`, etc.
>
> `switch` means it was intentional, while `drag` means it was unintentional
> (forced by Whirlwind, Roar, etc).

`|detailschange|POKEMON|DETAILS|HP STATUS` or 
`|-formechange|POKEMON|SPECIES|HP STATUS`

> The specified Pokémon has changed formes (via Mega Evolution, ability, etc.) 
> to `SPECIES`. If the forme change is permanent (Mega Evolution or a 
> Shaymin-Sky that is frozen), then `detailschange` will appear; otherwise, 
> the client will send `-formechange`.
>
> Syntax is the same as `|switch|` above.

`|replace|POKEMON|DETAILS|HP STATUS`

> Illusion has ended for the specified Pokémon. Syntax is the same as
> `|switch|` above, but remember that everything you thought you knew about the
> previous Pokémon is now wrong.
>
> `POKEMON` will be the NEW Pokémon ID - i.e. it will have the nickname of the
> Zoroark (or other Illusion user).

`|swap|POKEMON|POSITION`

> Moves already active `POKEMON` to active field `POSITION` where the
> leftmost position is 0 and each position to the right counts up by 1.

`|cant|POKEMON|REASON` or `|cant|POKEMON|REASON|MOVE`

> The Pokémon `POKEMON` could not perform a move because of the indicated
> `REASON` (such as paralysis, Disable, etc). Sometimes, the move it was
> trying to use is given.

`|faint|POKEMON`

> The Pokémon `POKEMON` has fainted.

### Minor actions

Minor actions are less important than major actions. In the official client,
they're usually displayed in small font if they have a message. Pretty much
anything that happens in a battle other than a switch or the fact that a move
was used is a minor action. So yes, the effects of a move such as damage or
stat boosts are minor actions.

`|-fail|POKEMON|ACTION`

> The specified `ACTION` has failed against the `POKEMON` targetted. The
> `ACTION` in question should be a move that fails due to its own mechanics.
> Moves (or effect activations) that fail because they're blocked by another
> effect should use `-block` instead.

`|-block|POKEMON|EFFECT|MOVE|ATTACKER`

> An effect targeted at `POKEMON` was blocked by `EFFECT`. This may optionally
> specify that the effect was a `MOVE` from `ATTACKER`. `[of]SOURCE` will note
> the owner of the `EFFECT`, in the case that it's not `EFFECT` (for instance,
> an ally with Aroma Veil.)

`|-notarget|POKEMON`

> A move has failed due to their being no target Pokémon `POKEMON`. `POKEMON` is
> not present in Generation 1. This action is specific to Generations 1-4 as in
> later Generations a failed move will display using `-fail`.

`|-miss|SOURCE|TARGET`

> The move used by the `SOURCE` Pokémon missed (maybe absent) the `TARGET`
> Pokémon.

`|-damage|POKEMON|HP STATUS`

> The specified Pokémon `POKEMON` has taken damage, and is now at
> `HP STATUS` (see `|switch|` for details).
>
> If `HP` is 0, `STATUS` should be ignored. The current behavior is for
> `STATUS` to be `fnt`, but this may change and should not be relied upon.

`|-heal|POKEMON|HP STATUS`

> Same as `-damage`, but the Pokémon has healed damage instead.

`|-sethp|POKEMON|HP`

> The specified Pokémon `POKEMON` now has `HP` hit points.

`|-status|POKEMON|STATUS`

> The Pokémon `POKEMON` has been inflicted with `STATUS`.

`|-curestatus|POKEMON|STATUS`

> The Pokémon `POKEMON` has recovered from `STATUS`.

`|-cureteam|POKEMON`

> The Pokémon `POKEMON` has used a move that cures its team of status effects, 
> like Heal Bell.

`|-boost|POKEMON|STAT|AMOUNT`

> The specified Pokémon `POKEMON` has gained `AMOUNT` in `STAT`, using the
> standard rules for Pokémon stat changes in-battle. `STAT` is a standard
> three-letter abbreviation fot the stat in question, so Speed will be `spe`,
> Special Defense will be `spd`, etc.

`|-unboost|POKEMON|STAT|AMOUNT`

> Same as `-boost`, but for negative stat changes instead.

`|-setboost|POKEMON|STAT|AMOUNT`

> Same as `-boost` and `-unboost`, but `STAT` is *set* to `AMOUNT` instead of
> boosted *by* `AMOUNT`. (For example: Anger Point, Belly Drum)

`|-swapboost|SOURCE|TARGET|STATS`

> Swaps the boosts from `STATS` between the `SOURCE` Pokémon and `TARGET`
> Pokémon. `STATS` takes the form of a comma-separated list of `STAT`
> abbreviations as described in `-boost`. (For example: Guard Swap, Heart
> Swap).

`|-invertboost|POKEMON`

> Invert the boosts of the target Pokémon `POKEMON`. (For example: Topsy-Turvy).

`|-clearboost|POKEMON`

> Clears all of the boosts of the target `POKEMON`. (For example: Clear Smog).

`|-clearallboost`

> Clears all boosts from all Pokémon on both sides. (For example: Haze).

`|-clearpositiveboost|TARGET|POKEMON|EFFECT`

> Clear the positive boosts from the `TARGET` Pokémon due to an `EFFECT` of the
> `POKEMON` Pokémon. (For example: 'move: Spectral Thief').

`|-clearnegativeboost|POKEMON`

> Clear the negative boosts from the target Pokémon `POKEMON`. (For example:
> usually as the result of a `[zeffect]`).

`|-copyboost|SOURCE|TARGET`

> Copy the boosts from `SOURCE` Pokémon to `TARGET` Pokémon (For example: Psych
> Up).

`|-weather|WEATHER`

> Indicates the weather that is currently in effect. If `|[upkeep]` is present,
> it means that `WEATHER` was active previously and is still in effect that
> turn. Otherwise, it means that the weather has changed due to a move or ability,
> or has expired, in which case `WEATHER` will be `none`.

`|-fieldstart|CONDITION`

> The field condition `CONDITION` has started. Field conditions are all effects that
> affect the entire field and aren't a weather. (For example: Trick Room, Grassy
> Terrain)

`|-fieldend|CONDITION`

> Indicates that the field condition `CONDITION` has ended.

`|-sidestart|SIDE|CONDITION`

> A side condition `CONDITION` has started on `SIDE`. Side conditions are all
> effects that affect one side of the field. (For example: Tailwind, Stealth
> Rock, Reflect)

`|-sideend|SIDE|CONDITION`

> Indicates that the side condition `CONDITION` ended for the given `SIDE`.

`|-swapsideconditions`

> Swaps side conditions between sides. Used for Court Change.

`|-start|POKEMON|EFFECT`

> A [*volatile* status](https://bulbapedia.bulbagarden.net/wiki/Status_condition#Volatile_status)
> has been inflicted on the `POKEMON` Pokémon by `EFFECT`. (For example:
> confusion, Taunt, Substitute).

`|-end|POKEMON|EFFECT`

> The volatile status from `EFFECT` inflicted on the `POKEMON` Pokémon has
> ended.

`|-crit|POKEMON`

> A move has dealt a critical hit against the `POKEMON`.

`|-supereffective|POKEMON`

> A move was super effective against the `POKEMON`.

`|-resisted|POKEMON`

> A move was not very effective against the `POKEMON`.

`|-immune|POKEMON`

> The `POKEMON` was immune to a move.

`|-item|POKEMON|ITEM|[from]EFFECT`

> The `ITEM` held by the `POKEMON` has been changed or revealed due to a move or 
> ability `EFFECT`.

`|-item|POKEMON|ITEM`

> `POKEMON` has just switched in, and its item `ITEM` is being announced to have a
> long-term effect (will not use `[from]`). Air Balloon is the only current user of
> this.

`|-enditem|POKEMON|ITEM|[from]EFFECT`

> The `ITEM` held by `POKEMON` has been destroyed by a move or ability (like
> Knock Off), and it now holds no item.
>
> This will be silent `[silent]` if the item's ownership was changed (with a move
> or ability like Thief or Trick), even if the move or ability would result in
> a Pokémon without an item.

`|-enditem|POKEMON|ITEM`

> `POKEMON`'s `ITEM` has destroyed itself (consumed Berries, Air Balloon). If a
> berry is consumed, it also has an additional modifier `|[eat]` to indicate
> that it was consumed.
>
> Sticky Barb does not announce itself with this or any other message when it
> changes hands.

`|-ability|POKEMON|ABILITY|[from]EFFECT`

> The `ABILITY` of the `POKEMON` has been changed due to a move/ability `EFFECT`.
>
> Note that Skill Swap does not send this message despite it changing abilities,
> because it does not reveal abilities when used between allies in a Double or
> Triple Battle.

`|-ability|POKEMON|ABILITY`

> `POKEMON` has just switched-in, and its ability `ABILITY` is being announced
> to have a long-term effect (will not use `[from]`).
>
> Effects that start at switch-in include Mold Breaker and Neutralizing Gas. It
> does not include abilities that activate once and don't have any long-term
> effects, like Intimidate (Intimidate should use `-activate`).

`|-endability|POKEMON`

> The `POKEMON` has had its ability suppressed by Gastro Acid.

`|-transform|POKEMON|SPECIES`

> The Pokémon `POKEMON` has transformed into `SPECIES` by the move Transform or
> the ability Imposter.

`|-mega|POKEMON|MEGASTONE`

> The Pokémon `POKEMON` used `MEGASTONE` to Mega Evolve.

`|-primal|POKEMON`

> The Pokémon `POKEMON` has reverted to its primal forme.

`|-burst|POKEMON|SPECIES|ITEM`

> The Pokémon `POKEMON` has used `ITEM` to Ultra Burst into `SPECIES`.

`|-zpower|POKEMON`

> The Pokémon `POKEMON` has used the z-move version of its move.

`|-zbroken|POKEMON`

> A z-move has broken through protect and hit the `POKEMON`.

`|-activate|EFFECT`

> A miscellaneous effect has activated. This is triggered whenever an effect could 
> not be better described by one of the other minor messages: for example, healing 
> abilities like Water Absorb simply use `-heal`.
>
> Items usually activate with `-end`, although items with two messages, like Berries
> ("POKEMON ate the Leppa Berry! POKEMON restored PP...!"), will send the "ate"
> message as `-eat`, and the "restored" message as `-activate`.

`|-hint|MESSAGE`

> Displays a message in parentheses to the client. Hint messages appear to explain and 
> clarify why certain actions, such as Fake Out and Mat Block failing, have occurred,  
> when there would normally be no in-game messages.

`|-center`

> Appears in Triple Battles when only one Pokémon remains on each side, to indicate
> that the Pokémon have been automatically centered.

`|-message|MESSAGE`

> Displays a miscellaneous message to the client. These messages are primarily used 
> for messages from game mods that aren't supported by the client, like rule clauses 
> such as Sleep Clause, or other metagames with custom messages for specific scenarios. 

`|-combine`

> A move has been combined with another (For example: Fire Pledge).

`|-waiting|SOURCE|TARGET`

> The `SOURCE` Pokémon has used a move and is waiting for the `TARGET` Pokémon
> (For example: Fire Pledge).

`|-prepare|ATTACKER|MOVE`
> The `ATTACKER` Pokémon is preparing to use a charge `MOVE` on an unknown target.
> (For example: Dig, Fly).

`|-prepare|ATTACKER|MOVE|DEFENDER`

> The `ATTACKER` Pokémon is preparing to use a charge `MOVE` on the `DEFENDER`.
> (For example: Sky Drop).

`|-mustrecharge|POKEMON`

> The Pokémon `POKEMON` must spend the turn recharging from a previous move.

`|-nothing`

> **DEPRECATED**: A move did absolutely nothing. (For example: Splash). In the
> future this will be of the form `|-activate|POKEMON|move: Splash`.

`|-hitcount|POKEMON|NUM`

> A multi-hit move hit the `POKEMON` `NUM` times.

`|-singlemove|POKEMON|MOVE`

> The Pokémon `POKEMON` used move `MOVE` which causes a temporary effect lasting
> the duration of the move. (For example: Grudge, Destiny Bond).

`|-singleturn|POKEMON|MOVE`

> The Pokémon `POKEMON` used move `MOVE` which causes a temporary effect lasting
> the duration of the turn. (For example: Protect, Focus Punch, Roost).


Sending decisions
-----------------

Using the Pokémon Showdown client, you can specify decisions with
`/choose CHOICE`, or, for move and switch decisions, just `/CHOICE` works as
well.

Using the simulator API, you would write `>p1 CHOICE` or `>p2 CHOICE` into the
battle stream.

### Possible choices

You can see the syntax in action by looking at the JavaScript console when
playing a Pokémon Showdown battle in a browser such as Chrome.

As an overview:

- `switch Pikachu`, `switch pikachu`, or `switch 2` are all valid `CHOICE`
  strings to switch to a Pikachu in slot 2.

- `move Focus Blast`, `move focusblast`, or `move 4` are all valid `CHOICE`
  strings to use Focus Blast, your active Pokemon's 4th move.

In Doubles, decisions are delimited by `,`. If you have a Manectric and a
Cresselia, `move Thunderbolt 1 mega, move Helping Hand -1` will make the
Manectric mega evolve and use Thunderbolt at the opponent in slot 1, while
Cresselia will use Helping Hand at Manectric.

To be exact, `CHOICE` is one of:

- `team TEAMSPEC`, during Team Preview, where `TEAMSPEC` is a list of pokemon
  slots.
  - For instance, `team 213456` will swap the first two Pokemon and keep all
    other pokemon in order.
  - `TEAMSPEC` does not have to be all pokemon: `team 5231` might be a choice
    in VGC.
  - `TEAMSPEC` does not need separators unless you have over 10 Pokémon, but
    in custom games, separate slots with `,`. For instance:
    `team 2, 1, 3, 4, 5, 6, 7, 8, 9, 10`

- `default`, to auto-choose a decision. This will be the first possible legal
  choice. This is what's used in VGC if you run out of Move Time.

- `undo`, to cancel a previously-made choice. This can only be done if the
  another player needs to make a choice and hasn't done so yet (or if you are
  calling `side.choose()` directly, which doesn't auto-continue when both
  players have made a choice).

- `POKEMONCHOICE` in Singles

- `POKEMONCHOICE, POKEMONCHOICE` in Doubles

`POKEMONCHOICE` is one of:

- `default`, to auto-choose a decision

- `pass`, to skip a slot in Doubles/Triples that doesn't need a decision (can
  be left off, but can be useful for readability, to mean "the pokemon in this
  slot is fainted and won't be making a move")

- `move MOVESPEC`, to make a move

- `move MOVESPEC mega`, to mega-evolve and make a move

- `move MOVESPEC zmove`, to use a z-move version of a move

- `move MOVESPEC max`, to Dynamax/Gigantamax and make a move

- `switch SWITCHSPEC`, to make a switch

`MOVESPEC` is:

- `MOVESLOTSPEC` or `MOVESLOTSPEC TARGETSPEC`
  - `MOVESLOTSPEC` is a move name (capitalization/spacing-insensitive) or
    1-based move slot number
  - `TARGETSPEC` is a 1-based target slot number. Add a `-` in front of it to
    refer to allies, and a `+` to refer to foes. Remember that slots go in
    opposite directions, like this:

         Triples       Doubles
        +3 +2 +1        +2 +1
        -1 -2 -3        -1 -2

    (Slot numbers are unnecessary in Singles: you can never choose a target in
    Singles.)

`SWITCHSPEC` is:

- a Pokémon nickname/species or 1-based slot number
  - Note that if you have multiple Pokémon with the same nickname/species, using the
    nickname/species will select the first unfainted one. If you want another Pokémon,
    you'll need to specify it by slot number.

Once a choice has been set for all players who need to make a choice, the
battle will continue.

If an invalid decision is sent (trying to switch when you're trapped by
Mean Look or something), you will receive a message starting with:

`|error|[Invalid choice] MESSAGE`

This will tell you to send a different decision. If your previous choice
revealed additional information (For example: a move disabled by Imprison
or a trapping effect), the error will be followed with a `|request|` command
to base your decision off of:

`|error|[Unavailable choice] MESSAGE`  
`|request|REQUEST`

### Choice requests

The protocol message to tell you that it's time for you to make a decision
is:

`|request|REQUEST`

> Gives a JSON object containing a request for a choice (to move or
> switch). To assist in your decision, `REQUEST.active` has information
> about your active Pokémon, and `REQUEST.side` has information about your
> your team as a whole.
>
> If you're using the simulator through a Pokémon Showdown server,
> `REQUEST.rqid` is an optional request ID. It will not exist if you're
> using the simulator directly through `import sim` or
> `./pokemon-showdown simulate-battle`.
>
> When sending decisions to a Pokémon Showdown server with `/choose`, you
> can add `|RQID` at the end. `RQID` is `REQUEST.rqid`, and it identifies
> which request the decision was intended for, making sure "Undo" doesn't
> cause the next decision to be sent for the wrong turn.

Example request object:

```
{
  "active": [
    {
      "moves": [
        {
          "move": "Light Screen",
          "id": "lightscreen",
          "pp": 48,
          "maxpp": 48,
          "target": "allySide",
          "disabled": false
        },
        {
          "move": "U-turn",
          "id": "uturn",
          "pp": 32,
          "maxpp": 32,
          "target": "normal",
          "disabled": false
        },
        {
          "move": "Knock Off",
          "id": "knockoff",
          "pp": 32,
          "maxpp": 32,
          "target": "normal",
          "disabled": false
        },
        {
          "move": "Roost",
          "id": "roost",
          "pp": 16,
          "maxpp": 16,
          "target": "self",
          "disabled": false
        }
      ]
    }
  ],
  "side": {
    "name": "Zarel",
    "id": "p2",
    "pokemon": [
      {
        "ident": "p2: Ledian",
        "details": "Ledian, L83, M",
        "condition": "227/227",
        "active": true,
        "stats": {
          "atk": 106,
          "def": 131,
          "spa": 139,
          "spd": 230,
          "spe": 189
        },
        "moves": [
          "lightscreen",
          "uturn",
          "knockoff",
          "roost"
        ],
        "baseAbility": "swarm",
        "item": "leftovers",
        "pokeball": "pokeball",
        "ability": "swarm"
      },
      {
        "ident": "p2: Pyukumuku",
        "details": "Pyukumuku, L83, F",
        "condition": "227/227",
        "active": false,
        "stats": {
          "atk": 104,
          "def": 263,
          "spa": 97,
          "spd": 263,
          "spe": 56
        },
        "moves": [
          "recover",
          "counter",
          "lightscreen",
          "reflect"
        ],
        "baseAbility": "innardsout",
        "item": "lightclay",
        "pokeball": "pokeball",
        "ability": "innardsout"
      },
      {
        "ident": "p2: Heatmor",
        "details": "Heatmor, L83, F",
        "condition": "277/277",
        "active": false,
        "stats": {
          "atk": 209,
          "def": 157,
          "spa": 222,
          "spd": 157,
          "spe": 156
        },
        "moves": [
          "fireblast",
          "suckerpunch",
          "gigadrain",
          "focusblast"
        ],
        "baseAbility": "flashfire",
        "item": "lifeorb",
        "pokeball": "pokeball",
        "ability": "flashfire"
      },
      {
        "ident": "p2: Reuniclus",
        "details": "Reuniclus, L78, M",
        "condition": "300/300",
        "active": false,
        "stats": {
          "atk": 106,
          "def": 162,
          "spa": 240,
          "spd": 178,
          "spe": 92
        },
        "moves": [
          "shadowball",
          "recover",
          "calmmind",
          "psyshock"
        ],
        "baseAbility": "magicguard",
        "item": "lifeorb",
        "pokeball": "pokeball",
        "ability": "magicguard"
      },
      {
        "ident": "p2: Minun",
        "details": "Minun, L83, F",
        "condition": "235/235",
        "active": false,
        "stats": {
          "atk": 71,
          "def": 131,
          "spa": 172,
          "spd": 189,
          "spe": 205
        },
        "moves": [
          "hiddenpowerice60",
          "nastyplot",
          "substitute",
          "thunderbolt"
        ],
        "baseAbility": "voltabsorb",
        "item": "leftovers",
        "pokeball": "pokeball",
        "ability": "voltabsorb"
      },
      {
        "ident": "p2: Gligar",
        "details": "Gligar, L79, M",
        "condition": "232/232",
        "active": false,
        "stats": {
          "atk": 164,
          "def": 211,
          "spa": 101,
          "spd": 148,
          "spe": 180
        },
        "moves": [
          "toxic",
          "stealthrock",
          "roost",
          "earthquake"
        ],
        "baseAbility": "hypercutter",
        "item": "eviolite",
        "pokeball": "pokeball",
        "ability": "hypercutter"
      }
    ]
  },
  "rqid": 3
}
```
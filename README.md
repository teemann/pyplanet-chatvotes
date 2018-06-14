# Pyplanet Chatvotes
## Deprecation
Some functions of this app are now deprecated and will probably be removed at some point as they
override the default pyplanet functions. These functions are:
 * Vote for restart
 * Vote for skip
 
## Description
Chatvotes as an app for pyplanet that adds a couple useful chat commands and a button with which players can
start a vote for additional time.

### New chat commands
 * [Deprecated] `/skip` or `/next`: Vote for the next map (uses the standard maniaplanet vote-system)
 * [Deprecated] `/restart` or `/res`: Vote for a map restart (uses the standard maniaplanet vote-system)
 * `/time` (the same as a click on the button): Start a vote for an additional hour on the map
   (uses the standard maniaplanet vote-system)
 * `//cancelvote`: Cancels an active vote (works only for standard maniaplanet votes)
 * `/afk`: Writes a message in the chat like [player] is away from keyboard and forces the player into spec.
 * `/re`: Writes a message in the chat like [player] has returned and forces the player out of spec.
 * `/nextmap`: Tells the player what the next map will be
 
### New settings
 * `max_votes`: Specifies the number of times a player can start a vote per map. Values < 1 = infinite.
 * `vote_cooldown`: Specifies the number of seconds a player has to wait before they can start a new vote after
 their last vote failed.
 * `chatvotes_show_bt`: Specifies if the button to vote for more time should be shown.
 
 **Note:** `max_votes` and `vote_cooldown` only work with `/skip` and `/restart` and their aliases.
 
 ### New UI elements
 The only UI element that is added is a button with the text `Request more time`. This button is located above the
 remaining time on the map. It can be disabled using the setting `chatvote_show_bt`.
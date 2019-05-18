from pyplanet.apps.config import AppConfig
from pyplanet.contrib.command import Command
from pyplanet.contrib.player.manager import Player
from pyplanet.contrib.setting import Setting
from pyplanet.apps.core.maniaplanet import callbacks as mp_signals
from pyplanet.contrib.map.exceptions import MapNotFound
from pyplanet.core.events import callback
from .view import VoteTimeView

import datetime
import logging
import functools


class Chatvotes(AppConfig):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.time_view = VoteTimeView(self, manager=self.context.ui)
        self.next_map_call = '''
            <methodCall>
                <methodName>NextMap</methodName>
            </methodCall>
        '''
        self.res_map_call = '''
                    <methodCall>
                        <methodName>RestartMap</methodName>
                    </methodCall>
                '''
        self.time_vote_call = '''
                    <methodCall>
                        <methodName>Echo</methodName>
                        <params>
                            <param>
                                <value><string>Play this map an additional hour?</string></value>
                            </param>
                            <param>
                                <value><string>teemann_add_time</string></value>
                            </param>
                        </params>
                    </methodCall>
                '''
        self.player_votes = {}
        self.time_limit = -1
        self.vote_time_limit = self.time_limit
        self.setting_show_bt = Setting('chatvotes_show_bt', 'Button request time', Setting.CAT_DESIGN,
                                       type=bool, description='Show the button to request more time',
                                       change_target=self.reload, default=True)
        self.setting_vote_time_ratio = Setting('chatvotes_time_ratio', 'Time vote ratio', Setting.CAT_GENERAL,
                                               type=float, description='The ratio needed for the additional-time-vote'
                                                                       'to pass. 0.5 = 50%', default=0.5)
        self.setting_vote_time_timeout = Setting('chatvotes_time_timeout', 'Time vote timeout', Setting.CAT_GENERAL,
                                                 type=int, description='The timeout of the additional-time-vote'
                                                                       'in milliseconds.', default=90000)

    async def display(self, logins=None):
        if await self.setting_show_bt.get_value():
            await self.time_view.display(player_logins=logins)

    async def hide_all(self):
        await self.time_view.hide()

    async def reload(self, *args, **kwargs):
        await self.hide_all()
        await self.display()

    async def on_init(self):
        await super().on_init()

    async def on_start(self):
        await super().on_start()
        settings = await self.instance.mode_manager.get_settings()
        if 'S_TimeLimit' in settings:
            self.time_limit = settings['S_TimeLimit']
        echo = callback.Callback('ManiaPlanet.Echo', 'maniaplanet', code='maniaplanet_echo', target=self.handle_echo)
        self.instance.signal_manager.register_signal(echo, app=None, callback=True)

        await self.instance.command_manager.register(
            Command('skip', aliases=['next'], admin=False, target=self.skip_vote))
        await self.instance.command_manager.register(
            Command('restart', aliases=['res'], admin=False, target=self.restart_vote))
        await self.instance.command_manager.register(
            Command('cancelvote', aliases=['cancel'], admin=True, target=self.cancel_vote))
        await self.instance.command_manager.register(Command('time', admin=False, target=self.vote_time))
        await self.instance.command_manager.register(Command('afk', admin=False, target=self.go_afk))
        await self.instance.command_manager.register(Command('re', admin=False, target=self.go_re))
        await self.instance.command_manager.register(Command('nextmap', admin=False, target=self.get_next_map))

        await self.context.setting.register(
            Setting('max_votes', 'Maximum votes per player and map', category=Setting.CAT_GENERAL, type=int,
                    description='Maximum number of votes a player can start on a map (<1 = infinite)', default=1))
        await self.context.setting.register(
            Setting('vote_cooldown', 'Minimum time between votes (sec)', category=Setting.CAT_GENERAL, type=int,
                    description='Minimum time a player has to wait until they can start a new vote'
                                ' after their last vote failed. In seconds', default=600))
        await self.context.setting.register(self.setting_show_bt)
        await self.context.setting.register(self.setting_vote_time_ratio)
        await self.context.setting.register(self.setting_vote_time_timeout)


        self.instance.signal_manager.listen(mp_signals.map.map_start, self.map_start)
        self.instance.signal_manager.listen(mp_signals.flow.podium_start, self.on_map_end)
        self.instance.signal_manager.listen(mp_signals.player.player_connect, self.on_connect)
        await self.display()

    async def on_stop(self):
        await super().on_stop()

    async def on_destroy(self):
        await super().on_destroy()

    async def on_connect(self, player, *args, **kwargs):
        await self.display(logins=[player.login])

    async def on_map_end(self, *args, **kwargs):
        await self.hide_all()

    async def map_start(self, *args, **kwargs):
        self.player_votes = {}
        await self.display()
        if self.time_limit != -1:
            settings = await self.instance.mode_manager.get_settings()
            if 'S_TimeLimit' in settings:
                tl = settings['S_TimeLimit']
                if tl == self.time_limit or tl != self.vote_time_limit:
                    return
            upd_settings = {'S_TimeLimit': self.time_limit}
            await self.instance.mode_manager.update_settings(upd_settings)

    async def check_vote(self, player):
        """

                :type player: Player
        """
        max_votes = await (await self.context.setting.get_setting('max_votes')).get_value()
        vote_cooldown = await (await self.context.setting.get_setting('vote_cooldown')).get_value()

        logging.debug('maxvotes: {}, cooldown: {}'.format(max_votes, vote_cooldown))

        vote = None
        if player.login in self.player_votes:
            vote = self.player_votes[player.login]
        if not vote:
            vote = Vote(player=player)
            self.player_votes[player.login] = vote
            return True
        else:
            tdiff = (datetime.datetime.now() - vote.last).total_seconds()
            if 0 < max_votes <= vote.count:
                await self.instance.chat('You cannot start a vote right now (max_votes: {})'.format(max_votes), player)
                return False
            if (datetime.datetime.now() - vote.last).total_seconds() <= vote_cooldown:
                await self.instance.chat(
                    'You cannot start a vote right now (you have to wait {} seconds)'.format(
                        int(vote_cooldown - tdiff + 1)),
                    player)
                return False
            vote.increment()
        return True

    async def skip_vote(self, player, data, *args, **kwargs):
        """

                :type player: Player
        """
        if not await self.check_vote(player=player):
            return

        logging.debug('skip requested by ' + player.login)
        await self.instance.gbx.multicall(
            self.instance.chat(player.nickname + ' $z$fa0$wrequested map skip.'),
            self.instance.gbx('CallVoteEx', self.next_map_call, 0.5, 90000, 1)
        )

    async def restart_vote(self, player, data, *args, **kwargs):
        """

        :type player: Player
        """
        if not await self.check_vote(player=player):
            return

        logging.debug('skip requested by ' + player.login)
        await self.instance.gbx.multicall(
            self.instance.chat(player.nickname + ' $z$fa0$wrequested map restart.'),
            self.instance.gbx('CallVoteEx', self.res_map_call, 0.5, 90000, 1)
        )

    async def cancel_vote(self, player, data, *args, **kwargs):
        """

        :type player: Player
        """

        if player.level >= Player.LEVEL_ADMIN:
            await self.instance.gbx.multicall(
                self.instance.gbx('CancelVote'),
                self.instance.chat('$z$fa0Admin {} $z$fa0cancelled the vote.'.format(player.nickname))
            )

    async def vote_time(self, player, data, *args, **kwargs):
        """

        :type player: Player
        """
        settings = await self.instance.mode_manager.get_settings()
        if 'S_TimeLimit' in settings:
            tl = settings['S_TimeLimit']
            if tl <= 0:
                await self.instance.chat('$f00This vote is only available when there is a time limit.', player)
                return
        ratio = await self.setting_vote_time_ratio.get_value()
        timeout = await self.setting_vote_time_timeout.get_value()
        await self.instance.gbx.multicall(
            self.instance.gbx('CallVoteEx', self.time_vote_call, ratio, timeout, 1),
            self.instance.chat(player.nickname + ' $z$fa0$wrequested additional time.')
        )

    async def go_afk(self, player, data, *args, **kwargs):
        """

        :type player: Player
        """
        info = await self.instance.gbx('GetPlayerInfo', player.login, 1)
        if info["SpectatorStatus"] & 1 == 0:
            await self.instance.gbx.multicall(
                self.instance.chat('{} $z$fffis away from keyboard.'.format(player.nickname)),
                self.instance.gbx('ForceSpectator', player.login, 3)
            )
        else:
            logging.debug('{} is already spectator'.format(player.login))

    async def go_re(self, player, data, *args, **kwargs):
        """

        :type player: Player
        """
        info = await self.instance.gbx('GetPlayerInfo', player.login, 1)
        if info['SpectatorStatus'] & 1 != 0:
            await self.instance.gbx.multicall(
                self.instance.chat('{} $z$fffhas returned.'.format(player.nickname)),
                self.instance.gbx('ForceSpectator', player.login, 2),
                self.instance.gbx('ForceSpectator', player.login, 0)
            )
        else:
            logging.debug('{} is no spectator'.format(player.login))

    async def get_next_map(self, player, data, *args, **kwargs):
        """

        :type player: Player
        """
        info = await self.instance.gbx('GetNextMapInfo')
        await self.instance.chat(
                'The next map will be {} $z$s$fffby {}.'.format(info['Name'], info['Author']), player.login)

    async def handle_echo(self, source, *args, **kwargs):
        s1, s2 = source
        if s1 == 'teemann_add_time':
            await self.instance.chat('$z$fa0$wAdded one additional hour to the timer.')
            sets = await self.instance.mode_manager.get_settings()
            if 'S_TimeLimit' in sets:
                tl = sets['S_TimeLimit']
                if tl != self.vote_time_limit:
                    self.time_limit = tl
                self.vote_time_limit = tl + 3600
                settings = {'S_TimeLimit': self.vote_time_limit}
                await self.instance.mode_manager.update_settings(settings)

class Vote:
    def __init__(self, player):
        self.count = 1
        self.player = player
        self.last = datetime.datetime.now()

    def increment(self):
        self.count += 1
        self.last = datetime.datetime.now()

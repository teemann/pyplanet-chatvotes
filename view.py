from pyplanet.views import TemplateView
import logging


class VoteTimeView(TemplateView):
    widget_x = 125
    widget_y = -5
    template_name = 'chatvotes/time_button.xml'

    def __init__(self, app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app
        self.id = 'pyplanet__widgets_time'

    async def get_context_data(self):
        context = await super().get_context_data()
        context.update({
            'pos_x': self.widget_x,
            'pos_y': self.widget_y
        })
        return context

    async def display(self, **kwargs):
        return await super().display(**kwargs)

    async def handle_catch_all(self, player, action, values, **kwargs):
        logging.debug('CatchAll: {}: {}'.format(player.login, action))
        if action.startswith('request_'):
            await self.app.vote_time(player, None)

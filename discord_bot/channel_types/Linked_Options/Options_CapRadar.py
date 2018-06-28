from . import Base_Feed
import discord
from functools import partial
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy.exc import IntegrityError

class Options_CapRadar(Base_Feed.base_activefeed):
    def __init__(self, insight_channel):
        assert isinstance(insight_channel, capRadar.capRadar)
        super().__init__(insight_channel)
        self.super_ids = [30,659]
        self.capital_ids = [547,485,1538]
        self.blops_ids = [898]

    def mention_options(self,message_object,group_type):
        __options = discord_options.mapper_index(self.cfeed.discord_client, message_object, timeout_seconds=45)
        __options.set_main_header("Select mention mode for this channel. On detected {} activity the bot "
                                  "can optionally mention @ here or @ everyone if the km occurred very recently.".format(group_type))
        __options.add_option(discord_options.option_returns_object("No mention", return_object=enum_mention.noMention))
        __options.add_option(discord_options.option_returns_object("@ here", return_object=enum_mention.here))
        __options.add_option(discord_options.option_returns_object("@ everyone", return_object=enum_mention.everyone))
        return __options

    def modify_groups(self,group_ids,mention_method,remove=False):
        db: Session = self.cfeed.service.get_session()
        try:
            if not remove:
                for i in group_ids:
                    __row: tb_Filter_groups = tb_Filter_groups.get_row(self.cfeed.channel_id,i,self.cfeed.service)
                    __row.mention = mention_method
                    db.merge(__row)
                db.commit()
                return "ok"
            else:
                for i in group_ids:
                    tb_Filter_groups.get_remove(self.cfeed.channel_id,i,self.cfeed.service)
                db.commit()
                return "ok"
        except Exception as ex:
            print(ex)
            return "An error occurred when attempting to set group tracking mode: {}".format(str(ex))
        finally:
            db.close()


    async def InsightOptionRequired_add(self, message_object: discord.Message):
        """Add or modify LY range for base system - Track targets within a specific LY range of an added system. Multiple systems can be added to a channel for a better spread."""
        def make_options(search_str):
            __options = discord_options.mapper_index(self.cfeed.discord_client, message_object, timeout_seconds=45)
            __options.set_main_header("Select the entity you wish to add.")
            db: Session = self.cfeed.service.get_session()

            def header_make(row_list:List[tb_systems],header_text):
                if len(row_list) > 0:
                    __options.add_header_row(header_text)
                    for i in row_list:
                        __options.add_option(discord_options.option_returns_object(name=i.name, return_object=i))
            try:
                header_make(db.query(tb_systems).filter(tb_systems.name.ilike("%{}%".format(search_str))).all(),"Systems")
                __options.add_header_row("Additional Options")
                __options.add_option(discord_options.option_returns_object("Search again",return_object=None))
            except Exception as ex:
                print(ex)
                db.rollback()
            finally:
                db.close()
                return __options

        __search = discord_options.mapper_return_noOptions(self.cfeed.discord_client,message_object,timeout_seconds=60)
        __search.set_main_header("Enter the name of a base system to track activity within range of.")
        __search.set_footer_text("Enter a name. Note: partial names are accepted: ")
        __selected_option = None
        while __selected_option is None:
            __search_name = await __search()
            __found_results = await self.cfeed.discord_client.loop.run_in_executor(None,partial(make_options,__search_name))
            __selected_option:tb_systems = await __found_results()
        __ly_range = discord_options.mapper_return_noOptions_requiresInt(self.cfeed.discord_client, message_object,
                                                            timeout_seconds=45)
        __ly_range.set_main_header("Enter the maximum LY radius to post KMs for the selected system.\n\n"
                                  "Only systems within your chosen LY range will appear in this feed.")
        __range = await __ly_range()
        function_call = partial(tb_channels.commit_list_entry,__selected_option,self.cfeed.channel_id,self.cfeed.service,maxly=__range)
        __code = await self.cfeed.discord_client.loop.run_in_executor(None, function_call)
        await message_object.channel.send(str(__code))
        if __code != "ok":
            raise None
        await self.cfeed.async_load_table()

    async def InsightOption_remove(self, message_object: discord.Message):
        """Remove base system - Removes a selected base system from the feed."""
        def remove_system(system_id):
            db:Session = self.cfeed.service.get_session()
            try:
                tb_Filter_systems.get_remove(channel_id=self.cfeed.channel_id,filter_id=system_id,service_module=self.cfeed.service)
                db.commit()
                return "ok"
            except Exception as ex:
                print(ex)
                return "An error occurred when attempting to remove a system: {}".format(str(ex))
            finally:
                db.close()

        def make_options():
            db:Session = self.cfeed.service.get_session()
            __remove = discord_options.mapper_index_withAdditional(self.cfeed.discord_client, message_object, timeout_seconds=60)
            __remove.set_main_header("Select the system you wish to remove as a base.")
            try:
                __remove.add_header_row("Systems currently set as bases for this feed")
                for i in db.query(tb_Filter_systems).filter(tb_Filter_systems.channel_id==self.cfeed.channel_id).all():
                    __representation = "System: {}-----LY Range: {}".format(str(i.object_item.name),str(i.max))
                    __remove.add_option(discord_options.option_returns_object(name=__representation,return_object=i.filter_id))
            except:
                db.rollback()
            finally:
                db.close()
                return __remove
        __options = await self.cfeed.discord_client.loop.run_in_executor(None,make_options)
        system_id = await __options()
        __code = await self.cfeed.discord_client.loop.run_in_executor(None,partial(remove_system,system_id))
        await message_object.channel.send(str(__code))
        if __code != "ok":
            raise None
        await self.cfeed.async_load_table()

    async def InsightOptionRequired_supers(self,message_object:discord.Message):
        """Super tracking - Enables or disables tracking of supercarriers/titans within range of bases."""
        __options = discord_options.mapper_return_yes_no(self.cfeed.discord_client,message_object,timeout_seconds=45)
        __options.set_main_header("Track supercarrier and titan activity in this channel?")
        __track_group_TF = await __options()
        if __track_group_TF:
            __mention_method = self.mention_options(message_object,"supercarrier/titan")
            __mention_enum = await __mention_method()
            __code = await self.cfeed.discord_client.loop.run_in_executor(None,partial(self.modify_groups,self.super_ids,__mention_enum))
        else:
            __code = await self.cfeed.discord_client.loop.run_in_executor(None,partial(self.modify_groups,self.super_ids,enum_mention.noMention,remove=True))
        await message_object.channel.send(__code)
        if __code != "ok":
            raise None
        await self.cfeed.async_load_table()

    async def InsightOptionRequired_capitals(self,message_object:discord.Message):
        """Capital tracking - Enables or disables tracking of capitals(dreads,carriers,FAX) within range of bases."""
        __options = discord_options.mapper_return_yes_no(self.cfeed.discord_client,message_object,timeout_seconds=45)
        __options.set_main_header("Track capital(dreads,carriers,FAX) activity in this channel?")
        __track_group_TF = await __options()
        if __track_group_TF:
            __mention_method = self.mention_options(message_object,"capital(dreads,carriers,FAX)")
            __mention_enum = await __mention_method()
            __code = await self.cfeed.discord_client.loop.run_in_executor(None,partial(self.modify_groups,self.capital_ids,__mention_enum))
        else:
            __code = await self.cfeed.discord_client.loop.run_in_executor(None,partial(self.modify_groups,self.capital_ids,enum_mention.noMention,remove=True))
        await message_object.channel.send(__code)
        if __code != "ok":
            raise None
        await self.cfeed.async_load_table()

    async def InsightOptionRequired_blops(self,message_object:discord.Message):
        """BLOPS tracking - Enables or disables tracking of blackops battleships within range of bases."""
        __options = discord_options.mapper_return_yes_no(self.cfeed.discord_client,message_object,timeout_seconds=45)
        __options.set_main_header("Track blackops battleship activity in this channel?")
        __track_group_TF = await __options()
        if __track_group_TF:
            __mention_method = self.mention_options(message_object,"blackops battleships")
            __mention_enum = await __mention_method()
            __code = await self.cfeed.discord_client.loop.run_in_executor(None,partial(self.modify_groups,self.blops_ids,__mention_enum))
        else:
            __code = await self.cfeed.discord_client.loop.run_in_executor(None,partial(self.modify_groups,self.blops_ids,enum_mention.noMention,remove=True))
        await message_object.channel.send(__code)
        if __code != "ok":
            raise None
        await self.cfeed.async_load_table()

    async def InsightOptionRequired_maxage(self,message_object:discord.Message):
        """Set max KM age - Sets the maximum KM age in minutes for kills to be posted to this channel. If a km occurred
        more than this many minutes ago it will not be posted to the channel."""
        def change_limit(new_limit):
            db: Session = self.cfeed.service.get_session()
            try:
                __row = tb_capRadar.get_row(self.cfeed.channel_id,self.cfeed.service)
                __row.max_km_age = new_limit
                db.merge(__row)
                db.commit()
                return "ok"
            except Exception as ex:
                print(ex)
                return "An error occurred when attempting to set max age: {}".format(str(ex))
            finally:
                db.close()

        __options = discord_options.mapper_return_noOptions_requiresInt(self.cfeed.discord_client,message_object,timeout_seconds=45)
        __options.set_main_header("Enter the maximum age in minutes for a KM to be posted to the channel. KMs "
                                  "occurring more than this many minutes ago will not be posted.")
        _max_age = await __options()
        __code = await self.cfeed.discord_client.loop.run_in_executor(None,partial(change_limit,_max_age))
        await message_object.channel.send(str(__code))
        if __code != "ok":
            raise None
        await self.cfeed.async_load_table()

from .. import capRadar
from discord_bot import discord_options
from database.db_tables import *
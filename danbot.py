import discord
from discord.ui import View, Button
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import random
import zipfile

import db

db.init_db()
load_dotenv()
token = os.getenv("BOTTOKEN")


handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='$', intents=intents)
thepath = os.getenv("THEPATH")

def getsize(mypath):
    total = 0
    for entry in os.scandir(mypath):
        if entry.is_file():
            total += entry.stat().st_size
        elif entry.is_dir():
            total += getsize(entry.path)
    return total

def diriterate(path, file):

    files = file
    for entry in os.scandir(path):
        if entry.is_file():
            if (entry.stat().st_size / (1024 **2)  >= 10) or zipfile.is_zipfile(entry.path):
                print(f"of id: {os.path.basename(path)}, skipped id: {os.path.basename(entry)}")
                continue
            else:
                if len(files[-1]) == 10:
                    files.append([])
                files[-1].append(discord.File(entry.path))
        elif entry.is_dir():
            diriterate(entry.path, files)

    return files

def get_valid_filepaths(path):
    if os.path.isfile(path):
        if (os.path.getsize(path)/ (1024**2) >= 10):
            print(f" file of id: {os.path.basename(path)} is too big")
        return [path]
    paths = []
    for entry in os.scandir(path):
        if entry.is_file():
            if (entry.stat().st_size / (1024**2) >= 10) or zipfile.is_zipfile(entry.path):
                print(f"of id: {os.path.basename(path)}, skipped: {os.path.basename(entry)}")
                continue
            paths.append(entry.path)
        elif entry.is_dir():
            paths.extend(get_valid_filepaths(entry.path))
    return paths

async def open_file_viewer(interaction, file_id, back_target):
    await interaction.response.defer()
    filepath = db.get_filepath(file_id)
    if not filepath or not os.path.exists(filepath):
        await interaction.response.edit_message(content=f"File not found. id: {file_id}", attachments=[], view=BackOnlyView(back_target))
        return

    filepaths = get_valid_filepaths(filepath)
    if not filepaths:
        await interaction.response.edit_message(content="No valid files (empty or all too big).", attachments=[], view=BackOnlyView(back_target))
        return

    view = FileBatchView(file_id, filepaths, batch_index=0, back_target=back_target)
    first_files = [discord.File(p) for p in view.batches[0]]
    view.message = interaction.message
    await interaction.edit_original_response(content=file_id, attachments=first_files, view=view)
    db.log_request(file_id, interaction.user.id)

class NavTarget:
    def __init__(self, builder, content):
        self.builder = builder  # a function that creates the previous view
        self.content = content  # the text that went with it

    def build(self):
        return self.builder()

class BackOnlyView(View):
    def __init__(self, back_target=None):
        super().__init__(timeout=120)
        self.message = None
        self.back_target = back_target
        self.build_buttons()

    async def on_timeout(self):
        if self.message:
            await self.message.edit(content="This menu timed out.", view=None)

    def build_buttons(self):
        self.clear_items()

        back_btn = Button(label="← Back", style=discord.ButtonStyle.danger)
        back_btn.callback = self.make_back_callback()
        self.add_item(back_btn)

    def make_back_callback(self):
        async def callback(interaction):
            new_view = self.back_target.build()
            new_view.message = interaction.message
            await interaction.response.edit_message(content=self.back_target.content, embed=None, attachments=[], view=new_view)
        return callback
    
class MenuListView(View):
    def __init__(self):
        super().__init__(timeout=120)
        self.message = None
        self.build_buttons()

    async def on_timeout(self):
        if self.message:
            await self.message.edit(content="This menu timed out.", view=None)

    def build_buttons(self):
        self.clear_items()
        tag_btn = Button(label="All Tags", style=discord.ButtonStyle.primary)
        tag_btn.callback = self.make_tags_callback(offset = 0, category = None)
        self.add_item(tag_btn)

        art_btn = Button(label="Artist Tags", style=discord.ButtonStyle.primary)
        art_btn.callback = self.make_tags_callback(offset = 0, category = "artist")
        self.add_item(art_btn)

        series_btn = Button(label="Series Tags", style=discord.ButtonStyle.primary)
        series_btn.callback = self.make_tags_callback(offset = 0, category = "copyright")
        self.add_item(series_btn)

        toptags_btn = Button(label="Top Tags", style=discord.ButtonStyle.primary)
        toptags_btn.callback = self.make_toptags_callback(offset = 0)
        self.add_item(toptags_btn)

        topfiles_btn = Button(label="Top Files RQS", style=discord.ButtonStyle.primary)
        topfiles_btn.callback = self.make_topfiles_callback(offset = 0)
        self.add_item(topfiles_btn)

        topfilescore_btn = Button(label="Top Files SCORE", style=discord.ButtonStyle.primary)
        topfilescore_btn.callback = self.make_topfilescore_callback(offset = 0)
        self.add_item(topfilescore_btn)

        stats_btn = Button(label="Bot Stats", style=discord.ButtonStyle.primary)
        stats_btn.callback = self.make_stats_callback()
        self.add_item(stats_btn)


    def make_tags_callback(self, offset=0, category=None):
        async def callback(interaction):
            back_target = NavTarget(
            lambda: MenuListView(),
            f"epic menu"
            )
            new_view = TagListView(offset=offset, back_target=back_target, category=category)
            new_view.message = interaction.message
            if category == "artist":
                await interaction.response.edit_message(content=f"Artist Tags: ", view=new_view)
            elif category == "copyright":
                await interaction.response.edit_message(content=f"Series Tags: ", view=new_view)        
            else:
                await interaction.response.edit_message(content=f"All Tags: ", view=new_view)          
        return callback

    def make_toptags_callback(self, offset=0):
        async def callback(interaction):
            back_target = NavTarget(
            lambda: MenuListView(),
            f"epic menu"
            )
            new_view = TagListView(offset=offset, back_target=back_target, sorting=True)
            new_view.message = interaction.message
            await interaction.response.edit_message(content=f"Top Tags by Requests:", view=new_view)          
        return callback

    def make_topfiles_callback(self, offset=0):
        async def callback(interaction):
            back_target = NavTarget(
            lambda: MenuListView(),
            f"epic menu"
            )
            new_view = FileListView(offset=offset, back_target=back_target, sorting=True)
            new_view.message = interaction.message
            await interaction.response.edit_message(content=f"Top Files by Requests:", view=new_view)          
        return callback

    def make_topfilescore_callback(self, offset=0):
        async def callback(interaction):
            back_target = NavTarget(
            lambda: MenuListView(),
            f"epic menu"
            )
            new_view = FileListView(offset=offset, back_target=back_target, sorting=False, scoring=True)
            new_view.message = interaction.message
            await interaction.response.edit_message(content=f"Top Files by Score:", view=new_view)          
        return callback

    def make_stats_callback(self):
        async def callback(interaction):
            total_requests = db.get_total_request_count()
            total_files = db.get_total_file_count()
            total_size = db.get_total_size()
            size_gb = total_size / (1024 ** 3)

            embed = discord.Embed(title="Bot Stats", color=discord.Color.blurple())
            embed.add_field(name="Total Files", value=str(total_files), inline=True)
            embed.add_field(name="Total Requests", value=str(total_requests), inline=True)
            embed.add_field(name="Total Size", value=f"{size_gb:.2f} GB", inline=True)

            back_target = NavTarget(
                lambda: MenuListView(),
                f"epic menu"
                )
            new_view = BackOnlyView(back_target=back_target)
            new_view.message = interaction.message
            await interaction.response.edit_message(content=None, embed=embed, attachments=[], view=new_view)
        return callback
    
class TagListView(View):
    def __init__(self, offset=0, category=None, back_target=None, sorting=False):
        super().__init__(timeout=120)
        self.offset = offset
        self.category = category
        self.back_target = back_target
        self.sorting=sorting
        if sorting:
            self.tags = db.get_top_requested_tags(limit=20, offset=offset, category=category)
        else:
            self.tags = db.get_tags(limit=20, offset=offset, category=category)
        self.message = None
        self.build_buttons()

    async def on_timeout(self):
        if self.message:
            await self.message.edit(content="This menu timed out.", view=None)

    def make_title(self):
        if self.category and not self.sorting:
            return f"Commonest {self.category}s:"
        elif self.sorting:
            return f"Top tags by requests:"
        else:
            return "All tags:"
    
    def build_buttons(self):
        self.clear_items()
        for tag_id, tag_name, freq in self.tags:
            btn = Button(label=f"{tag_name} ({freq})", style=discord.ButtonStyle.primary)
            btn.callback = self.make_tag_callback(tag_id, tag_name)
            self.add_item(btn)

        if self.offset > 0:
            prev_btn = Button(label="◀ Prev", style=discord.ButtonStyle.secondary)
            prev_btn.callback = self.make_page_callback(new_offset=self.offset - 20)
            self.add_item(prev_btn)

        if len(self.tags) == 20:
            next_btn = Button(label="Next ▶", style=discord.ButtonStyle.secondary)
            next_btn.callback = self.make_page_callback(new_offset=self.offset + 20)
            self.add_item(next_btn)

        back_btn = Button(label="← Back", style=discord.ButtonStyle.danger)
        back_btn.callback = self.make_back_callback()
        self.add_item(back_btn)
            
        pg_btn = Button(label=f"page: {1 + self.offset//20}", disabled=True)
        self.add_item(pg_btn)

    def make_page_callback(self, new_offset):
        async def callback(interaction):
            new_view = TagListView(offset=new_offset, back_target=self.back_target, category=self.category, sorting=self.sorting)
            new_view.message = interaction.message
            mything = self.make_title()
            await interaction.response.edit_message(content=f"{mything}", view=new_view)
        return callback
    
    def make_back_callback(self):
        async def callback(interaction):
            new_view = self.back_target.build()
            new_view.message = interaction.message
            await interaction.response.edit_message(content=self.back_target.content, attachments=[], view=new_view)
        return callback
    
    def make_tag_callback(self, tag_id, tag_name):
        async def callback(interaction):
            back_target = NavTarget(
            lambda: TagListView(offset=self.offset, category=self.category, sorting=self.sorting, back_target=self.back_target),
            self.make_title()
            )
            new_view = FileListView(tag_id=tag_id, tag_name=tag_name, offset=0, back_target=back_target)
            new_view.message = interaction.message
            await interaction.response.edit_message(content=f"Files tagged '{tag_name}':", view=new_view)
        return callback

class FileListView(View):
    def __init__(self, tag_id=None, tag_name=None, offset=0, back_target=None, sorting=False, scoring=False):
        super().__init__(timeout=120)
        self.tag_id = tag_id
        self.tag_name = tag_name
        self.offset = offset
        self.back_target = back_target
        self.sorting = sorting
        self.scoring = scoring
        if self.sorting:
            self.file_ids = db.get_top_requested_files(limit=20, offset=self.offset)
        elif self.scoring:
            self.file_ids = db.get_top_files_by_score(limit=20, offset=self.offset)
        else:
            self.file_ids = db.get_files_for_tag(tag_id, limit=20, offset=self.offset)
        self.message = None
        self.build_buttons()

    async def on_timeout(self):
        if self.message:
            await self.message.edit(content="This menu timed out.", view=None)

    def build_buttons(self):
        self.clear_items()
        if not self.tag_name:
            for file_id, req_count in self.file_ids:
                btn = Button(label=f"{file_id} ({req_count})", style=discord.ButtonStyle.primary)
                btn.callback = self.make_file_callback(file_id)
                self.add_item(btn)
        else:
            for file_id in self.file_ids:
                btn = Button(label=file_id, style=discord.ButtonStyle.primary)
                btn.callback = self.make_file_callback(file_id)
                self.add_item(btn)

        if self.offset > 0:
            prev_btn = Button(label="◀ Prev", style=discord.ButtonStyle.secondary)
            prev_btn.callback = self.make_page_callback(self.offset - 20)
            self.add_item(prev_btn)

        if len(self.file_ids) == 20:
            next_btn = Button(label="Next ▶", style=discord.ButtonStyle.secondary)
            next_btn.callback = self.make_page_callback(self.offset + 20)
            self.add_item(next_btn)

        back_btn = Button(label="← Back", style=discord.ButtonStyle.danger)
        back_btn.callback = self.make_back_callback()
        self.add_item(back_btn)

        pg_btn = Button(label=f"page: {1 + self.offset//20}", disabled=True)
        self.add_item(pg_btn)

    def make_page_callback(self, new_offset):
        async def callback(interaction):
            new_view = FileListView(self.tag_id, self.tag_name, back_target=self.back_target, offset=new_offset, sorting=self.sorting, scoring=self.scoring)
            new_view.message = interaction.message
            if not self.tag_name:
                await interaction.response.edit_message(content=f"Top Files: ", view=new_view)
            else:
                await interaction.response.edit_message(content=f"Files tagged '{self.tag_name}':", view=new_view)
        return callback
    
    def make_file_callback(self, file_id):
        async def callback(interaction):
            back_target = NavTarget(
                lambda: FileListView(self.tag_id, self.tag_name, offset=self.offset, back_target=self.back_target, sorting=self.sorting, scoring=self.scoring),
                f"Top Files: " if not self.tag_name else f"Files tagged '{self.tag_name}':" 
            )            
            await open_file_viewer(interaction, file_id, back_target)
        return callback
    
    #region for old file callback
    # def make_file_callback(self, file_id):
    #     async def callback(interaction):
    #         filepath = db.get_filepath(file_id)
    #         if filepath and os.path.isdir(filepath):
    #             print(f"directory selected (thru tags func), {filepath}")
    #             batches = diriterate(filepath, [[]])
    #             first = True
    #             for batch in batches:
    #                 if not batch:
    #                     continue
    #                 if len(batch) == 1:
    #                     try:
    #                         if first:
    #                             await interaction.response.send_message(file=batch[0], content=file_id)
    #                             first = False
    #                         else:
    #                             await interaction.followup.send(file=batch[0], content=file_id)
                            
    #                     except:
    #                         print(f"error in sending singlebatch")
    #                         if first:
    #                             await interaction.response.send_message("error in sending singlebatch")
    #                         else:
    #                             await interaction.followup.send("error in sending singlebatch")
    #                 else:
    #                     try:
    #                         if first:
    #                             await interaction.response.send_message(files=batch, content=file_id)
    #                             first = False
    #                         else:
    #                             await interaction.followup.send(files=batch, content=file_id)
                            
    #                     except:
    #                         print(f"error in sending multibatch, id: {file_id}")
    #                         if first:
    #                             await interaction.response.send_message(f"error in sending multibatch, id: {file_id}")
    #                             first = False
    #                         else:
    #                             await interaction.followup.send(f"error in sending multibatch, id: {file_id}")

    #             db.log_request(file_id, interaction.user.id)

    #         elif filepath and os.path.exists(filepath):
    #             print(f"file selected (thru tags func), {filepath}")
    #             try:
    #                 await interaction.response.send_message(file=discord.File(filepath), content=file_id)
    #                 db.log_request(file_id, interaction.user.id)
    #             except Exception as e:
    #                 print(f"file too big, id: {file_id}")
    #                 await interaction.response.send_message(f"file too big, id: {file_id}")
    #         else:
    #             await interaction.response.send_message(f"File not found on disk? id: {file_id}", ephemeral=True)
    #     return callback
    #endregion

    def make_back_callback(self):
        async def callback(interaction):
            new_view = self.back_target.build()
            new_view.message = interaction.message
            await interaction.response.edit_message(content=self.back_target.content, attachments=[], view=new_view)
        return callback

#region class TopFilesView(View):
#     def __init__(self, offset=0):
#         super().__init__(timeout=120)
#         self.offset = offset
#         self.rows = db.get_top_requested_files(limit=20, offset=offset)
#         self.message = None
#         self.build_buttons()

#     async def on_timeout(self):
#         if self.message:
#             await self.message.edit(content="This menu timed out.", view=None)

#     def build_buttons(self):
#         self.clear_items()
#         for file_id, req_count in self.rows:
#             btn = Button(label=f"{file_id} ({req_count})", style=discord.ButtonStyle.primary)
#             btn.callback = self.make_file_callback(file_id)
#             self.add_item(btn)

#         if self.offset > 0:
#             prev_btn = Button(label="◀ Prev", style=discord.ButtonStyle.secondary)
#             prev_btn.callback = self.make_page_callback(self.offset - 20)
#             self.add_item(prev_btn)

#         if len(self.rows) == 20:
#             next_btn = Button(label="Next ▶", style=discord.ButtonStyle.secondary)
#             next_btn.callback = self.make_page_callback(self.offset + 20)
#             self.add_item(next_btn)

#         back_btn = Button(label="← Back to menu", style=discord.ButtonStyle.danger)
#         back_btn.callback = self.make_back_callback()
#         self.add_item(back_btn)

#         pg_btn = Button(label=f"page: {1 + self.offset//20}", disabled=True)
#         self.add_item(pg_btn)

#     def make_page_callback(self, new_offset):
#         async def callback(interaction):
#             new_view = TopFilesView(offset=new_offset)
#             new_view.message = interaction.message
#             await interaction.response.edit_message(content="Top requested files:", view=new_view)
#         return callback

#     def make_back_callback(self):
#         async def callback(interaction):
#             new_view = StatsMenuView()
#             new_view.message = interaction.message
#             await interaction.response.edit_message(content="Stats menu:", view=new_view)
#         return callback

#     def make_file_callback(self, file_id):
#         async def callback(interaction):
#             back_target = NavTarget(
#                 lambda: TopFilesView(offset=self.offset),
#                 f"Top requested files:"
#             )
#             await open_file_viewer(interaction, file_id, back_target)
#         return callback
#endregion

class FileBatchView(View):
    def __init__(self, file_id, filepaths, batch_index=0, back_target=None):
        super().__init__(timeout=120)
        self.file_id = file_id
        self.filepaths = filepaths
        self.batches = [filepaths[i:i+10] for i in range(0, len(filepaths), 10)]
        self.batch_index = batch_index
        self.back_target = back_target
        self.message = None
        self.build_buttons()

    async def on_timeout(self):
        if self.message:
            await self.message.edit(content="This menu timed out.", view=None)

    def build_buttons(self):
        self.clear_items()
        if self.batch_index > 0:
            prev_btn = Button(label="◀ Prev", style=discord.ButtonStyle.secondary)
            prev_btn.callback = self.make_page_callback(self.batch_index - 1)
            self.add_item(prev_btn)
        if self.batch_index < len(self.batches) - 1:
            next_btn = Button(label="Next ▶", style=discord.ButtonStyle.secondary)
            next_btn.callback = self.make_page_callback(self.batch_index + 1)
            self.add_item(next_btn)
        pg_btn = Button(label=f"batch {self.batch_index+1}/{len(self.batches)}", disabled=True)
        self.add_item(pg_btn)
        if self.back_target:
            back_btn = Button(label="← Back", style=discord.ButtonStyle.danger)
            back_btn.callback = self.make_back_callback()
            self.add_item(back_btn)

    def make_page_callback(self, new_index):
        async def callback(interaction):
            new_view = FileBatchView(self.file_id, self.filepaths, batch_index=new_index, back_target=self.back_target)
            new_view.message = interaction.message
            fresh_files = [discord.File(p) for p in new_view.batches[new_index]]
            await interaction.response.edit_message(content=self.file_id, attachments=fresh_files, view=new_view)
        return callback
    
    def make_back_callback(self):
        async def callback(interaction):
            new_view = self.back_target.build()
            new_view.message = interaction.message
            await interaction.response.edit_message(content=self.back_target.content, attachments=[], view=new_view)
        return callback

@bot.command()
@commands.cooldown(1, 10, commands.BucketType.user)
async def menu(ctx):
    view = MenuListView()
    view.message = await ctx.send("epic menu", view=view)

@bot.event
async def on_ready():
    print(f"{bot.user.name} is ready")


@bot.event
async def on_message(message):
    await bot.process_commands(message)



@bot.command()
@commands.cooldown(1, 2, commands.BucketType.user)
async def dan(ctx):
    limit = 3
    sentany = False
    for i in range(limit):
        items = os.listdir(thepath)
        item = os.path.join(thepath, random.choice(items))
        if os.path.isdir(item):
            print(f"directory selected, {os.path.basename(item)}")
            files = diriterate(item, [[]])
            
            for each in files:
                if not each:
                    continue
                if len(each) == 1:
                    try: 
                        await ctx.send(file=each[0], content=f"{os.path.basename(item)}")
                        sentany = True
                    except: 
                        await ctx.send(f"skipping single")
                else:
                    try:
                        await ctx.send(files=each, content=f"{os.path.basename(item)}")
                        sentany = True
                    except:
                        await ctx.send(f"skipping multi")
            if sentany:
                db.ensure_file_logged(os.path.basename(item), item)
                db.log_request(os.path.basename(item), ctx.author.id)
                return
            else:
                print("too big, retrying")
                await ctx.send("retrying with new item")
        elif zipfile.is_zipfile(item):
            print(f"zip selected, {os.path.basename(item)}")
            continue
        else:
            print(f"file selected, {os.path.basename(item)}")
            try: 
                await ctx.send(file=discord.File(item), content=f"{os.path.basename(item)}")
                item_id = os.path.splitext(os.path.basename(item))[0]  # strip extension
                db.ensure_file_logged(item_id, item)
                db.log_request(item_id, ctx.author.id)
                return
            except:
                print("too big")
                await ctx.send(f"auto trying again")



bot.run(token, log_handler=handler, log_level=logging.DEBUG)
import os
import datetime
import discord
import random
import discord.ui
import sys
import subprocess
from discord.ext import commands
from discord import app_commands
from discord.ui import Select, View, Modal, TextInput, Button

client = commands.Bot(command_prefix='.', intents=discord.Intents.all())

@client.event
async def on_ready():
    await client.change_presence(status=discord.Status.online, activity=discord.Game('constructed by estcban'))
    await client.tree.sync()
    print(f'Successfully logged in as {client.user}')


class ChannelModal(Modal, title='Channel Creation'):
    category_input = TextInput(
        label='Category Name(s)',
        placeholder='Single or multiple (separate with ;)',
        required=False,
        max_length=100
    )

    channel_input = TextInput(
        label='Channel Name(s)',
        placeholder='Single or multiple (separate with ;)',
        required=True,
        max_length=100
    )

    position_input = TextInput(
        label='Channel Position(s) (1-50)',
        placeholder='Single or multiple (separate with ;)',
        required=False,
        max_length=50
    )

    def __init__(self):
        super().__init__()

class RetryView(View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="", emoji="✅", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        modal = ChannelModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="", emoji="❌", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.message.delete()

@client.tree.command(name="createchannel", description="Create multiple channels and categories with positions")
async def createchannel(interaction: discord.Interaction):
    modal = ChannelModal()

    async def modal_callback(interaction: discord.Interaction):
        # Split inputs by semicolon and clean whitespace
        categories = [cat.strip() for cat in modal.category_input.value.split(';') if cat.strip()] if modal.category_input.value else []
        channels = [chan.strip().lower() for chan in modal.channel_input.value.split(';') if chan.strip()]
        positions = [pos.strip() for pos in modal.position_input.value.split(';') if pos.strip()] if modal.position_input.value else []

        # Validate positions
        if positions:
            try:
                positions = [int(pos) for pos in positions]
                if any(pos < 1 or pos > 50 for pos in positions):
                    embed = discord.Embed(
                        title="Error",
                        description="All positions must be between 1 and 50.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, view=RetryView(), ephemeral=True)
                    return
            except ValueError:
                embed = discord.Embed(
                    title="Error",
                    description="All positions must be valid numbers between 1 and 50.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, view=RetryView(), ephemeral=True)
                return

        # Extend positions list if it's shorter than channels list
        positions.extend([None] * (len(channels) - len(positions)))

        # Check for existing channels
        existing_channels = []
        for channel_name in channels:
            if discord.utils.get(interaction.guild.channels, name=channel_name):
                existing_channels.append(channel_name)

        if existing_channels:
            embed = discord.Embed(
                title="Error",
                description=f"The following channels already exist: {', '.join(existing_channels)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, view=RetryView(), ephemeral=True)
            return

        try:
            created_channels = []
            created_categories = []

            # If categories are specified
            if categories:
                # Handle multiple categories
                for category_name in categories:
                    category = discord.utils.get(interaction.guild.categories, name=category_name)

                    if not category:
                        category = await interaction.guild.create_category(category_name)
                        created_categories.append(category_name)

            # Create channels
            for i, channel_name in enumerate(channels):
                if categories:
                    # If we have multiple categories, cycle through them
                    category_index = i % len(categories)
                    category_name = categories[category_index]
                    category = discord.utils.get(interaction.guild.categories, name=category_name)

                    channel = await interaction.guild.create_text_channel(channel_name, category=category)

                    # Set position if specified
                    if positions[i] is not None:
                        await channel.move(beginning=True, offset=positions[i] - 1, category=category)

                    created_channels.append(f"#{channel_name} (in {category_name}" + 
                                         (f" at position {positions[i]}" if positions[i] else "") + ")")
                else:
                    # Create channel without category if no categories specified
                    channel = await interaction.guild.create_text_channel(channel_name)
                    created_channels.append(f"#{channel_name}")

            # Create success embed
            embed = discord.Embed(
                title="Success",
                color=discord.Color.green()
            )

            if created_categories:
                embed.add_field(
                    name="Created Categories",
                    value="\n".join(created_categories),
                    inline=False
                )

            embed.add_field(
                name="Created Channels",
                value="\n".join(created_channels),
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except discord.Forbidden:
            embed = discord.Embed(
                title="Error",
                description="I don't have permission to create channels or categories.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            embed = discord.Embed(
                title="Error",
                description=f"An unexpected error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    modal.on_submit = modal_callback
    await interaction.response.send_modal(modal)

class RoleManagementView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="Create Role", style=discord.ButtonStyle.green, custom_id="create")
    async def create_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RoleCreationModal())

    @discord.ui.button(label="Rename Role", style=discord.ButtonStyle.blurple, custom_id="rename") 
    async def rename_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RoleRenameModal())

    @discord.ui.button(label="Change Color", style=discord.ButtonStyle.primary, custom_id="color")
    async def change_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RoleColorModal())

    @discord.ui.button(label="Delete Role", style=discord.ButtonStyle.red, custom_id="delete")
    async def delete_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RoleDeleteModal())

class RoleCreationModal(Modal, title="Create New Role"):
    def __init__(self):
        super().__init__()
        self.add_item(TextInput(
            label="Role Names (separate with ;)",
            placeholder="Enter role names...",
            required=False
        ))
        self.add_item(TextInput(
            label="Role Color (hex code or name)", 
            placeholder="#FF0000;#00FF00 or red;blue;green",
            required=False
        ))
        self.add_item(TextInput(
            label="Position",
            placeholder="Enter position number (1 = highest)",
            required=False
        ))
        self.add_item(TextInput(
            label="Assign To Users (separate with ;)",
            placeholder="Enter usernames",
            required=False
        ))

    async def on_submit(self, interaction: discord.Interaction):
        role_names = self.children[0].value.strip().split(';')
        color_inputs = self.children[1].value.strip().split(';')
        position_inputs = self.children[2].value.strip().split(';')
        usernames = [u.strip() for u in self.children[3].value.strip().split(';') if u.strip()]

        # Extend color inputs if needed
        if len(color_inputs) < len(role_names):
            color_inputs.extend([''] * (len(role_names) - len(color_inputs)))

        # Extend position inputs if needed
        if len(position_inputs) < len(role_names):
            position_inputs.extend([''] * (len(role_names) - len(position_inputs)))

        COLORS = {
            "red": discord.Color.red(),
            "blue": discord.Color.blue(),
            "green": discord.Color.green(),
            "yellow": discord.Color.yellow(),
            "purple": discord.Color.purple(),
            "orange": discord.Color.orange(),
            "black": discord.Color.default(),
            "white": discord.Color.from_rgb(255, 255, 255),
            "pink": discord.Color.from_rgb(255, 192, 203),
            "cyan": discord.Color.teal()
        }

        created_roles = []
        relocated_roles = []
        errors = []
        role_assignments = []
        role_unassignments = []

        for i, (role_name, color_input, position_input) in enumerate(zip(role_names, color_inputs, position_inputs)):
            role_name = role_name.strip()
            color_input = color_input.strip()
            position_input = position_input.strip()

            # Check if role exists
            existing_role = discord.utils.get(interaction.guild.roles, name=role_name)

            # Set color
            if color_input:
                if color_input.startswith('#'):
                    try:
                        hex_value = int(color_input[1:], 16)
                        role_color = discord.Color(hex_value)
                    except ValueError:
                        role_color = discord.Color.default()
                else:
                    role_color = COLORS.get(color_input.lower(), discord.Color.default())
            else:
                role_color = discord.Color.default()

            if existing_role:
                if position_input:
                    try:
                        position = int(position_input)
                        await existing_role.edit(position=len(interaction.guild.roles) - position)
                        relocated_roles.append(existing_role)
                    except ValueError:
                        errors.append(f"Invalid position number for role '{role_name}'")

                # Handle role assignment/unassignment for existing role
                if usernames:
                    for username in usernames:
                        member = discord.utils.get(interaction.guild.members, name=username)
                        if member:
                            if existing_role in member.roles:
                                try:
                                    await member.remove_roles(existing_role)
                                    role_unassignments.append(existing_role)
                                except discord.Forbidden:
                                    errors.append(f"Could not unassign role from {username}")
                            else:
                                try:
                                    await member.add_roles(existing_role)
                                    role_assignments.append(existing_role)
                                except discord.Forbidden:
                                    errors.append(f"Could not assign role to {username}")
                continue

            if role_name:
                try:
                    role = await interaction.guild.create_role(
                        name=role_name,
                        color=role_color,
                        reason=f"Role created by {interaction.user}"
                    )
                    if position_input:
                        try:
                            position = int(position_input)
                            await role.edit(position=len(interaction.guild.roles) - position)
                        except ValueError:
                            errors.append(f"Invalid position number for role '{role_name}'")

                    # Assign role to users if specified
                    if usernames:
                        for username in usernames:
                            member = discord.utils.get(interaction.guild.members, name=username)
                            if member:
                                try:
                                    await member.add_roles(role)
                                    role_assignments.append(role)
                                except discord.Forbidden:
                                    errors.append(f"Could not assign role to {username}")

                    created_roles.append(role)
                except discord.Forbidden:
                    errors.append(f"Missing permissions to create role '{role_name}'")
                except discord.HTTPException:
                    errors.append(f"Failed to create role '{role_name}'")

        # Create response embed
        if created_roles or relocated_roles or role_assignments or role_unassignments:
            embed = discord.Embed(
                title="✨ Role Management Results",
                color=created_roles[0].color if created_roles else discord.Color.green(),
                timestamp=datetime.datetime.now()
            )

            if created_roles:
                embed.add_field(
                    name="Created Roles",
                    value="\n".join([f"• {role.name}" for role in created_roles]),
                    inline=False
                )

            if relocated_roles:
                embed.add_field(
                    name="Relocated Roles",
                    value="\n".join([f"• {role.name}" for role in relocated_roles]),
                    inline=False
                )

            if role_assignments:
                embed.add_field(
                    name="Roles Assigned",
                    value="\n".join([f"• {role.name} to {', '.join(usernames)}" for role in role_assignments]),
                    inline=False
                )

            if role_unassignments:
                embed.add_field(
                    name="Roles Unassigned",
                    value="\n".join([f"• {role.name} from {', '.join(usernames)}" for role in role_unassignments]),
                    inline=False
                )

            if errors:
                embed.add_field(
                    name="Errors",
                    value="\n".join([f"• {error}" for error in errors]),
                    inline=False
                )

            embed.set_footer(text=f"Managed by {interaction.user}")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            error_embed = discord.Embed(
                title="❌ Role Management Failed",
                description="No roles were created or modified",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            if errors:
                error_embed.add_field(
                    name="Errors",
                    value="\n".join([f"• {error}" for error in errors]),
                    inline=False
                )
            error_embed.set_footer(text=f"Requested by {interaction.user}")
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class RoleColorModal(Modal, title="Change Role Color"):
    def __init__(self):
        super().__init__()
        self.add_item(TextInput(
            label="Role Name",
            placeholder="Enter the role name...",
            required=True
        ))
        self.add_item(TextInput(
            label="New Color (hex code)",
            placeholder="#FF0000",
            required=True
        ))

    async def on_submit(self, interaction: discord.Interaction):
        role_name = self.children[0].value.strip()
        color_input = self.children[1].value.strip()

        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if role:
            try:
                if color_input.startswith('#'):
                    hex_value = int(color_input[1:], 16)
                    new_color = discord.Color(hex_value)
                else:
                    raise ValueError("Invalid hex code")

                await role.edit(color=new_color)
                embed = discord.Embed(
                    title="🎨 Role Color Changed",
                    description=f"Color changed for role '{role_name}'",
                    color=new_color,
                    timestamp=datetime.datetime.now()
                )
                embed.set_footer(text=f"Modified by {interaction.user}")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except ValueError:
                await interaction.response.send_message("Invalid hex color code! Use format #RRGGBB", ephemeral=True)
        else:
            await interaction.response.send_message(f"Role '{role_name}' not found.", ephemeral=True)

class RoleRenameModal(Modal, title="Rename Role"):
    def __init__(self):
        super().__init__()
        self.add_item(TextInput(
            label="Current Role Name",
            placeholder="Enter the current role name...",
            required=True
        ))
        self.add_item(TextInput(
            label="New Role Name",
            placeholder="Enter the new role name...",
            required=True
        ))

    async def on_submit(self, interaction: discord.Interaction):
        current_name = self.children[0].value.strip()
        new_name = self.children[1].value.strip()

        # Check if the new role name already exists
        existing_role = discord.utils.get(interaction.guild.roles, name=new_name)
        if existing_role:
            error_embed = discord.Embed(
                title="❌ Role Rename Failed",
                description=f"A role with the name '{new_name}' already exists",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            error_embed.set_footer(text=f"Requested by {interaction.user}")
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        role = discord.utils.get(interaction.guild.roles, name=current_name)
        if role:
            await role.edit(name=new_name)
            embed = discord.Embed(
                title="✏️ Role Renamed",
                description=f"Role successfully renamed from '{current_name}' to '{new_name}'",
                color=role.color,
                timestamp=datetime.datetime.now()
            )
            embed.set_footer(text=f"Modified by {interaction.user}")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            error_embed = discord.Embed(
                title="❌ Role Not Found",
                description=f"Role '{current_name}' does not exist",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            error_embed.set_footer(text=f"Requested by {interaction.user}")
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class RoleDeleteModal(Modal, title="Delete Role"):
    def __init__(self):
        super().__init__()
        self.add_item(TextInput(
            label="Role Names (separate with ;)",
            placeholder="Enter the role names to delete...",
            required=True
        ))

    async def on_submit(self, interaction: discord.Interaction):
        role_names = [name.strip() for name in self.children[0].value.strip().split(';')]
        roles_to_delete = []
        not_found_roles = []

        for role_name in role_names:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role:
                roles_to_delete.append(role)
            else:
                not_found_roles.append(role_name)

        if not roles_to_delete:
            error_embed = discord.Embed(
                title="❌ Roles Not Found",
                description="None of the specified roles exist",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            if not_found_roles:
                error_embed.add_field(
                    name="Missing Roles",
                    value="\n".join([f"• {name}" for name in not_found_roles]),
                    inline=False
                )
            error_embed.set_footer(text=f"Requested by {interaction.user}")
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        class DeleteConfirmationView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.button(label="✅", style=discord.ButtonStyle.green)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                deleted_roles = []
                failed_roles = []

                for role in roles_to_delete:
                    try:
                        await role.delete()
                        deleted_roles.append(role.name)
                    except discord.Forbidden:
                        failed_roles.append(role.name)

                embed = discord.Embed(
                    title="🗑️ Role Deletion Results",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.now()
                )

                if deleted_roles:
                    embed.add_field(
                        name="Deleted Roles",
                        value="\n".join([f"• {name}" for name in deleted_roles]),
                        inline=False
                    )

                if failed_roles:
                    embed.add_field(
                        name="Failed to Delete",
                        value="\n".join([f"• {name}" for name in failed_roles]),
                        inline=False
                    )

                if not_found_roles:
                    embed.add_field(
                        name="Roles Not Found",
                        value="\n".join([f"• {name}" for name in not_found_roles]),
                        inline=False
                    )

                embed.set_footer(text=f"Deleted by {interaction.user}")
                await interaction.response.send_message(embed=embed, ephemeral=True)

            @discord.ui.button(label="❌", style=discord.ButtonStyle.red)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                embed = discord.Embed(
                    title="🚫 Deletion Cancelled",
                    description="Role deletion has been cancelled",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now()
                )
                embed.set_footer(text=f"Cancelled by {interaction.user}")
                await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = discord.Embed(
            title="🗑️ Delete Roles",
            description="Are you sure you want to delete the following roles?",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )

        roles_info = []
        for role in roles_to_delete:
            member_count = len(role.members)
            roles_info.append(f"• {role.name} ({member_count} members)")

        embed.add_field(
            name="Roles to Delete",
            value="\n".join(roles_info),
            inline=False
        )

        if not_found_roles:
            embed.add_field(
                name="Roles Not Found",
                value="\n".join([f"• {name}" for name in not_found_roles]),
                inline=False
            )

        embed.set_footer(text=f"Requested by {interaction.user}")
        await interaction.response.send_message(embed=embed, view=DeleteConfirmationView(), ephemeral=True)

@client.tree.command(name="role", description="Manage server roles")
async def role(interaction: discord.Interaction):
    if not interaction.guild.me.guild_permissions.manage_roles:
        error_embed = discord.Embed(
            title="❌ Permission Denied",
            description="I don't have permission to manage roles!",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        error_embed.set_footer(text=f"Requested by {interaction.user}")
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return

    embed = discord.Embed(
        title="🎭 Role Management",
        description="Select an action below to manage roles:",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="Available Actions", value=
        "🟢 Create Role - Create new role(s)\n"
        "🔵 Rename Role - Rename existing role\n"
        "🎨 Change Color - Change role color\n"
        "🔴 Delete Role - Delete existing role\n"
        "🔒 Tutorial - Utilize the /information command to learn more about the bot.\n"
    )
    embed.set_footer(text=f"Requested by {interaction.user}")

    await interaction.response.send_message(embed=embed, view=RoleManagementView(), ephemeral=True)

@client.tree.command(name="information", description="How to use the role management system properply.")
async def info(interaction: discord.Interaction):
    if not interaction.guild.me.guild_permissions.manage_roles:
        error_embed = discord.Embed(
            title="❌ Permission Denied",
            description="I don't have permission to manage roles!",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        error_embed.set_footer(text=f"Requested by {interaction.user}")
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return

    embed = discord.Embed(
        title="Tutorial",
        description="Learn more about utilizing this bot!",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="Functions", value=
        "CREATE ROLES - The create command - the most unique, diverse command amid the buttons. It comes with many, many functions that allows you to do an array of things, but here are the things that have been implemented this far.\n"
        "\n"
        "TO CREATE MULTIPLE ROLES - To create multiple roles, you must insert the seperate the roles you would like to make by a semi-colon. EXAMPLE: Manager; Staff Management.\n"
        "\n"
        "TO RELOCATE/POSITION ROLES WHEN USING MULTIPLE ROLES FUNCTION - To relocate multiple roles, you must insert the seperate the numbers you would like to make by a semi-colon. EXAMPLE: Manager; Staff Management. 2; 3\n"
        "\n"
        "TO CHANGE ROLE COLOR WHEN USING MULTIPLE ROLES FUNCTION - To change the color of multiple roles, you must insert the seperate hex codes/colors names by using semi-colon. EXAMPLE: Manager; Staff Management. #FF0000; #00FF00 // red; blue\n"
        "\n"
        "TO ASSIGN ROLES TO MULTIPLE USERS - To assign roles to multiple users, separate usernames with semi-colons. EXAMPLE: user1; user2; user3\n"
        "\n"
        "TO DELETE MULTIPLE ROLES - To delete multiple roles at once, separate role names with semi-colons. EXAMPLE: role1; role2; role3"
    )
    embed.set_footer(text=f"Requested by {interaction.user}")

    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="restart", description="Restarts the bot")
@app_commands.default_permissions(administrator=True)
async def restart(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="🔄 Bot Restart",
            description="Initiating bot restart...",
            color=discord.Color.yellow()
        )
        embed.set_footer(text=f"Requested by {interaction.user}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

        new_embed = discord.Embed(
            title="🔄 Bot Restart",
            description="Bot is restarting...\nPlease wait a moment.",
            color=discord.Color.orange()
        )
        new_embed.set_footer(text=f"Requested by {interaction.user}")

        message = await interaction.original_response()
        await message.edit(embed=new_embed)

        await message.delete(delay=2)

        file_path = os.path.abspath(sys.argv[0])

        if os.name == 'nt': # Windows
            with open("restart.bat", "w") as bat_file:
                bat_file.write(f'''
@echo off
timeout /t 1 /nobreak >nul
python "{file_path}"
del "%~f0"
''')
            subprocess.Popen("restart.bat")
        else: # Linux/Mac
            with open("restart.sh", "w") as sh_file:
                sh_file.write(f'''
sleep 1
python3 "{file_path}"
rm "$0"
''')
            subprocess.Popen(['sh', 'restart.sh'])

        await client.close()

    except discord.Forbidden:
        error_embed = discord.Embed(
            title="❌ Permission Denied",
            description="I don't have permission to perform this action!",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        error_embed.set_footer(text=f"Requested by {interaction.user}")
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        error_embed.set_footer(text=f"Requested by {interaction.user}")
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

TOKEN = "MTMwNzM5NDExNDUwNDg4ODQzMA.GoPYyc.V93-9CLlsJXrOv_8AcJdL78e9zYJwBDsjwZz4k"
client.run(TOKEN)
#!/usr/bin/env python3
"""
SCP FOUNDATION: CONTAINMENT BREACH — A Text-Based RPG
Secure. Contain. Protect.
"""

import sys
import os
import time
import random

# --- ANSI Color Codes ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
RED_BOLD = "\033[1;31m"
GREEN_BOLD = "\033[1;32m"
YELLOW_BOLD = "\033[1;33m"
BLUE_BOLD = "\033[1;34m"
MAGENTA_BOLD = "\033[1;35m"
CYAN_BOLD = "\033[1;36m"
WHITE_BOLD = "\033[1;37m"


# --- Utility Functions ---
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def slow_print(text, delay=0.03):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def print_divider(char="─", width=60):
    print(char * width)


def print_header(text):
    print(f"\n{CYAN_BOLD}{'═' * 60}{RESET}")
    print(f"{CYAN_BOLD}  {text.center(56)}{RESET}")
    print(f"{CYAN_BOLD}{'═' * 60}{RESET}\n")


def get_choice(options, prompt="What do you do?"):
    print(f"\n{YELLOW_BOLD}{prompt}{RESET}")
    for i, option in enumerate(options, 1):
        print(f"  {WHITE_BOLD}[{i}]{RESET} {option}")
    print(f"  {WHITE_BOLD}[0]{RESET} View Status")
    while True:
        try:
            choice = input(f"\n{GREEN}> {RESET}").strip()
            if choice == "0":
                return 0
            choice = int(choice)
            if 1 <= choice <= len(options):
                return choice
            print(f"{RED}Invalid choice. Try again.{RESET}")
        except ValueError:
            print(f"{RED}Please enter a number.{RESET}")


def yes_no(prompt):
    while True:
        answer = input(f"{YELLOW}{prompt} (y/n): {RESET}").strip().lower()
        if answer in ("y", "yes"):
            return True
        elif answer in ("n", "no"):
            return False
        print(f"{RED}Please answer yes or no.{RESET}")


def roll_chance(percent):
    return random.randint(1, 100) <= percent


# --- Item Definitions ---
ITEMS = {
    "flashlight": {
        "name": "Flashlight",
        "desc": "A heavy-duty flashlight. Essential in dark areas.",
        "type": "tool",
        "usable": True,
    },
    "keycard_1": {
        "name": "Level 1 Keycard",
        "desc": "Basic access keycard.",
        "type": "keycard",
        "level": 1,
    },
    "keycard_2": {
        "name": "Level 2 Keycard",
        "desc": "Standard access keycard. Opens most facility doors.",
        "type": "keycard",
        "level": 2,
    },
    "keycard_3": {
        "name": "Level 3 Keycard",
        "desc": "Senior personnel keycard. Opens research areas.",
        "type": "keycard",
        "level": 3,
    },
    "keycard_4": {
        "name": "Level 4 Keycard",
        "desc": "High-security keycard. Opens containment zones.",
        "type": "keycard",
        "level": 4,
    },
    "keycard_5": {
        "name": "O5 Keycard",
        "desc": "Supreme access keycard. Opens everything.",
        "type": "keycard",
        "level": 5,
    },
    "first_aid": {
        "name": "First Aid Kit",
        "desc": "Restores 30 HP.",
        "type": "consumable",
        "usable": True,
        "heal": 30,
    },
    "medkit": {
        "name": "Military Medkit",
        "desc": "Restores 60 HP.",
        "type": "consumable",
        "usable": True,
        "heal": 60,
    },
    "gas_mask": {
        "name": "Gas Mask",
        "desc": "Protects from airborne hazards. Reduces sanity loss.",
        "type": "armor",
        "usable": False,
    },
    "body_armor": {
        "name": "Tactical Body Armor",
        "desc": "Reduces physical damage by 25%.",
        "type": "armor",
        "usable": False,
    },
    "pistol": {
        "name": "9mm Pistol",
        "desc": "Standard-issue sidearm.",
        "type": "weapon",
        "usable": False,
        "damage": 15,
        "ammo": 12,
        "max_ammo": 12,
    },
    "shotgun": {
        "name": "Combat Shotgun",
        "desc": "Devastating at close range.",
        "type": "weapon",
        "usable": False,
        "damage": 35,
        "ammo": 6,
        "max_ammo": 6,
    },
    "ammo_pistol": {
        "name": "Pistol Ammo Box",
        "desc": "12 rounds of 9mm.",
        "type": "ammo",
        "usable": True,
        "ammo_type": "pistol",
        "amount": 12,
    },
    "ammo_shotgun": {
        "name": "Shotgun Shells",
        "desc": "6 shotgun shells.",
        "type": "ammo",
        "usable": True,
        "ammo_type": "shotgun",
        "amount": 6,
    },
    "radio": {
        "name": "Walkie-Talkie",
        "desc": "Can contact other survivors.",
        "type": "tool",
        "usable": True,
    },
    "document_breach": {
        "name": "Breach Report",
        "desc": "Details about the breach. Someone helped SCP-079...",
        "type": "document",
        "usable": True,
    },
    "document_682": {
        "name": "SCP-682 Termination Log",
        "desc": "All attempts to destroy SCP-682 have failed.",
        "type": "document",
        "usable": True,
    },
    "scp_714": {
        "name": "SCP-714",
        "desc": "A jade ring that protects from many SCP effects and calms the mind.",
        "type": "anomalous",
        "usable": True,
    },
    "sedative": {
        "name": "Sedative Syringe",
        "desc": "Can knock out certain entities temporarily.",
        "type": "consumable",
        "usable": True,
    },
    "battery": {
        "name": "Batteries",
        "desc": "Recharges your flashlight.",
        "type": "consumable",
        "usable": True,
    },
    "key_containment": {
        "name": "Containment Override Key",
        "desc": "Reactivates containment systems in the Control Room.",
        "type": "key",
        "usable": False,
    },
    "elevator_code": {
        "name": "Elevator Code Note",
        "desc": "The code to the surface elevator: 4729.",
        "type": "document",
        "usable": True,
    },
}


# --- SCP Data ---
SCP_DATA = {
    "SCP-173": {
        "name": "SCP-173",
        "nickname": "The Sculpture",
        "object_class": "Euclid",
        "desc": "A concrete sculpture that moves when not observed. Contact means instant death.",
        "hp": 999,
        "attack": 999,
        "can_kill": False,
    },
    "SCP-096": {
        "name": "SCP-096",
        "nickname": "The Shy Guy",
        "object_class": "Euclid",
        "desc": "If you see its face, it will hunt you relentlessly. Nothing stops it.",
        "hp": 9999,
        "attack": 9999,
        "can_kill": False,
    },
    "SCP-049": {
        "name": "SCP-049",
        "nickname": "The Plague Doctor",
        "object_class": "Euclid",
        "desc": "Kills with a touch, reanimating victims. Polite but deadly.",
        "hp": 200,
        "attack": 999,
        "can_kill": True,
    },
    "SCP-682": {
        "name": "SCP-682",
        "nickname": "Hard-to-Destroy Reptile",
        "object_class": "Keter",
        "desc": "Immense reptilian creature. Regenerates from anything. Hates all life.",
        "hp": 50000,
        "attack": 80,
        "can_kill": True,
    },
    "SCP-079": {
        "name": "SCP-079",
        "nickname": "Old AI",
        "object_class": "Euclid",
        "desc": "Sentient AI that caused the breach. Manipulative and resentful.",
        "hp": 0,
        "attack": 0,
        "can_kill": False,
    },
    "SCP-939": {
        "name": "SCP-939",
        "nickname": "With Many Voices",
        "object_class": "Keter",
        "desc": "Blind predators that mimic human voices to lure prey.",
        "hp": 150,
        "attack": 45,
        "can_kill": True,
    },
}


# --- Player ---
class Player:
    def __init__(self, name, role):
        self.name = name
        self.role = role
        if role == "Researcher":
            self.max_hp, self.hp = 80, 80
            self.max_sanity, self.sanity = 120, 120
            self.stealth, self.combat, self.knowledge = 7, 3, 9
        elif role == "Security":
            self.max_hp, self.hp = 120, 120
            self.max_sanity, self.sanity = 100, 100
            self.stealth, self.combat, self.knowledge = 5, 8, 4
        else:
            self.max_hp, self.hp = 150, 150
            self.max_sanity, self.sanity = 90, 90
            self.stealth, self.combat, self.knowledge = 6, 9, 5
        self.inventory = []
        self.wearing_714 = False
        self.has_flashlight_on = False
        self.scp_encountered = set()
        self.rooms_visited = set()
        self.objectives_complete = set()
        self.flags = set()
        self.turns = 0

    def get_keycard_level(self):
        return max(
            (
                ITEMS[i]["level"]
                for i in self.inventory
                if ITEMS[i]["type"] == "keycard"
            ),
            default=0,
        )

    def has_item(self, item_id):
        return item_id in self.inventory

    def add_item(self, item_id):
        if item_id not in self.inventory:
            self.inventory.append(item_id)
            return True
        return False

    def remove_item(self, item_id):
        if item_id in self.inventory:
            self.inventory.remove(item_id)
            return True
        return False

    def get_best_weapon(self):
        weapons = [i for i in self.inventory if ITEMS[i]["type"] == "weapon"]
        return max(weapons, key=lambda w: ITEMS[w]["damage"]) if weapons else None

    def get_weapon_damage(self):
        w = self.get_best_weapon()
        return (ITEMS[w]["damage"] + self.combat * 2) if w else self.combat * 2

    def get_damage_reduction(self):
        r = 0
        if self.has_item("body_armor"):
            r += 0.25
        if self.wearing_714:
            r += 0.10
        return min(r, 0.5)

    def take_damage(self, raw):
        actual = int(raw * (1 - self.get_damage_reduction()))
        self.hp = max(0, self.hp - actual)
        return actual

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def lose_sanity(self, amount):
        if self.wearing_714:
            amount = amount // 3
        if self.has_item("gas_mask"):
            amount = int(amount * 0.8)
        self.sanity = max(0, self.sanity - amount)

    def gain_sanity(self, amount):
        self.sanity = min(self.max_sanity, self.sanity + amount)

    def is_alive(self):
        return self.hp > 0

    def is_sane(self):
        return self.sanity > 0

    def print_status(self):
        print(f"\n{BOLD}{'═' * 50}{RESET}")
        print(f"{WHITE_BOLD}  {self.name} — {self.role}{RESET}")
        print(f"{BOLD}{'─' * 50}{RESET}")
        hp_pct = self.hp / self.max_hp
        hp_c = GREEN_BOLD if hp_pct > 0.6 else YELLOW_BOLD if hp_pct > 0.3 else RED_BOLD
        filled = int(hp_pct * 30)
        print(
            f"  {hp_c}HP: [{'█' * filled}{'░' * (30 - filled)}] {self.hp}/{self.max_hp}{RESET}"
        )
        sp = self.sanity / self.max_sanity
        sc = CYAN_BOLD if sp > 0.6 else YELLOW_BOLD if sp > 0.3 else RED_BOLD
        sf = int(sp * 30)
        print(
            f"  {sc}SAN: [{'█' * sf}{'░' * (30 - sf)}] {self.sanity}/{self.max_sanity}{RESET}"
        )
        print(f"{BOLD}{'─' * 50}{RESET}")
        print(
            f"  {DIM}Combat:{self.combat}  Stealth:{self.stealth}  Knowledge:{self.knowledge}{RESET}"
        )
        print(f"  {DIM}Keycard Level: {self.get_keycard_level()}{RESET}")
        w = self.get_best_weapon()
        if w:
            print(
                f"  {DIM}Weapon: {ITEMS[w]['name']} (DMG:{self.get_weapon_damage()}, Ammo:{ITEMS[w]['ammo']}){RESET}"
            )
        if self.wearing_714:
            print(f"  {MAGENTA_BOLD}SCP-714: ACTIVE{RESET}")
        print(f"{BOLD}{'─' * 50}{RESET}")
        if self.inventory:
            print(
                f"  {DIM}Inventory: {', '.join(ITEMS[i]['name'] for i in self.inventory)}{RESET}"
            )
        else:
            print(f"  {DIM}Inventory: Empty{RESET}")
        print(f"{BOLD}{'═' * 50}{RESET}\n")


# --- Room ---
class Room:
    def __init__(self, rid, name, desc, dark=False):
        self.id = rid
        self.name = name
        self.desc = desc
        self.dark = dark
        self.exits = {}
        self.locked_exits = {}
        self.items = []
        self.scp_present = None
        self.visited = False

    def add_exit(self, direction, room_id, keycard_level=0):
        self.exits[direction] = room_id
        if keycard_level > 0:
            self.locked_exits[direction] = keycard_level

    def get_available_exits(self, player):
        available = {}
        for d, rid in self.exits.items():
            if d in self.locked_exits:
                available[d] = (
                    rid if player.get_keycard_level() >= self.locked_exits[d] else None
                )
            else:
                available[d] = rid
        return available


# --- Game Engine ---
class Game:
    def __init__(self):
        self.player = None
        self.rooms = {}
        self.current_room = None
        self.game_over = False
        self.game_won = False
        self.ending = None

    def run(self):
        self.show_title()
        self.character_creation()
        self.setup_world()
        self.show_intro()
        self.main_loop()
        self.show_ending()

    def show_title(self):
        clear_screen()
        print(f"""{RED_BOLD}
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║   ██████╗ ██████╗ ███████╗   ██████╗ ███████╗██╗  ██╗   ║
    ║  ██╔════╝ ██╔══██╗██╔════╝   ██╔══██╗██╔════╝██║  ██║   ║
    ║  ██║  ███╗██████╔╝█████╗     ██████╔╝███████╗███████║   ║
    ║  ██║   ██║██╔══██╗██╔══╝     ██╔═══╝ ╚════██║██╔══██║   ║
    ║  ╚██████╔╝██║  ██║███████╗   ██║     ███████║██║  ██║   ║
    ║   ╚═════╝ ╚═╝  ╚═╝╚══════╝   ╚═╝     ╚══════╝╚═╝  ╚═╝   ║
    ║                                                          ║
    ║         ███╗   ██╗███████╗██╗  ██╗██╗   ██╗             ║
    ║         ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║             ║
    ║         ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║             ║
    ║         ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║             ║
    ║         ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝             ║
    ║         ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝              ║
    ║                                                          ║
    ║              C O N T A I N M E N T   B R E A C H        ║
    ║                   A Text-Based RPG                       ║
    ║                                                          ║
    ║          Secure. Contain. Protect.                       ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
{RESET}""")
        input(f"{DIM}  Press ENTER to begin...{RESET}")

    def character_creation(self):
        clear_screen()
        print_header("PERSONNEL FILE")
        name = ""
        while not name:
            name = input(f"{YELLOW}  Enter your name: {RESET}").strip()
        print(f"\n{WHITE}Select your role:{RESET}\n")
        print(
            f"  {CYAN_BOLD}[1]{RESET} {CYAN}Researcher{RESET} — {DIM}High knowledge & sanity. Low combat. Level 2 Keycard.{RESET}"
        )
        print(
            f"  {RED_BOLD}[2]{RESET} {RED}Security Guard{RESET} — {DIM}Balanced. Has pistol. Level 1 Keycard.{RESET}"
        )
        print(
            f"  {MAGENTA_BOLD}[3]{RESET} {MAGENTA}MTF Operative{RESET} — {DIM}High HP & combat. Low sanity. Shotgun + Armor. Level 3 Keycard.{RESET}"
        )
        roles = {"1": "Researcher", "2": "Security", "3": "MTF"}
        while True:
            c = input(f"\n{GREEN}> {RESET}").strip()
            if c in roles:
                role = roles[c]
                break
            print(f"{RED}Invalid choice.{RESET}")
        self.player = Player(name, role)
        if role == "Researcher":
            for i in ["keycard_2", "flashlight", "document_breach"]:
                self.player.add_item(i)
        elif role == "Security":
            for i in ["keycard_1", "pistol", "flashlight"]:
                self.player.add_item(i)
        else:
            for i in ["keycard_3", "shotgun", "flashlight", "body_armor"]:
                self.player.add_item(i)
        print(f"\n{GREEN_BOLD}Personnel file created. Welcome, {name}.{RESET}")
        time.sleep(1)

    def setup_world(self):
        R = self.rooms
        R["office"] = Room(
            "office",
            "Your Office",
            "A small, cluttered office. Papers scattered across the desk. Emergency lights cast an eerie red glow. "
            "A photo of SCP-096 lies face-down — someone was careful about that. "
            "The door hangs slightly ajar. Distant alarms wail.",
        )
        R["main_hall"] = Room(
            "main_hall",
            "Main Hallway",
            "A long corridor connecting major sections. Flickering lights create dancing shadows. "
            "Signs point toward Light Containment, Heavy Containment, Medical Bay, and Entrance Zone. "
            "Blood smears trail along the wall toward Heavy Containment.",
        )
        R["light_cont"] = Room(
            "light_cont",
            "Light Containment Zone — Hub",
            "A circular hub with corridors to multiple containment chambers. Every containment door is open. "
            "Warning lights flash red. Something scrapes in one corridor. The air smells of concrete dust.",
        )
        R["scp173"] = Room(
            "scp173",
            "SCP-173's Containment Chamber",
            "A large chamber streaked with feces and blood. The door has been wrenched open. "
            "SCP-173 stands perfectly still in the center. Its featureless face seems to stare right at you. "
            "Don't. Blink.",
            dark=True,
        )
        R["scp173"].scp_present = "SCP-173"
        R["scp049"] = Room(
            "scp049",
            "SCP-049's Containment Chamber",
            "A sterile white room that feels filthy. A plague doctor figure stands in the center, hands clasped. "
            "It tilts its head. 'Ah,' it says calmly. 'A visitor. Have you come for the cure?'",
        )
        R["scp049"].scp_present = "SCP-049"
        R["scp096_hall"] = Room(
            "scp096_hall",
            "Corridor Outside SCP-096's Cell",
            "A reinforced corridor. The cell door has been blown open from inside. "
            "SCP-096 sits in the corner, arms wrapped around knees, face hidden. "
            "It hasn't noticed you. Yet. A document on the floor contains a photograph.",
        )
        R["heavy_cont"] = Room(
            "heavy_cont",
            "Heavy Containment Zone — Hub",
            "The deeper you go, the worse things get. Thicker walls, dimmer lighting. "
            "Acid burns mark the floor near one corridor. A low, guttural growling echoes from ahead.",
        )
        R["scp682"] = Room(
            "scp682",
            "SCP-682's Containment Chamber",
            "A massive chamber filled with hydrochloric acid. SCP-682 is nowhere to be seen — "
            "the acid pool is partially drained. Claw marks score the walls twenty feet high. "
            "A gaping hole in the far wall. It's out.",
        )
        R["scp682"].scp_present = "SCP-682"
        R["server"] = Room(
            "server",
            "Server Room",
            "Rows of servers hum despite the chaos. An old microcomputer sits on a desk, screen glowing. "
            "SCP-079's containment terminal. The screen reads: 'I've been waiting for you.'",
        )
        R["server"].scp_present = "SCP-079"
        R["medbay"] = Room(
            "medbay",
            "Medical Bay",
            "In shambles. Overturned beds, scattered supplies, too much blood. "
            "A body in the corner twitches occasionally. Some supplies remain in locked cabinets.",
        )
        R["armory"] = Room(
            "armory",
            "Armory",
            "Mostly looted. Racks once holding weapons are empty. A few locked cases against the back wall. "
            "Someone scratched 'DON'T OPEN 682'S DOOR' into the metal.",
        )
        R["control"] = Room(
            "control",
            "Facility Control Room",
            "The nerve center. Banks of monitors show camera feeds — mostly static. "
            "The main console has a slot for a containment override key. "
            "The elevator to the surface is accessible from here.",
        )
        R["entrance"] = Room(
            "entrance",
            "Entrance Zone",
            "Transition area between underground and surface. Abandoned checkpoints. "
            "The main elevator requires a code. Blast doors separate this area from the outside.",
        )
        R["tunnel"] = Room(
            "tunnel",
            "Maintenance Tunnels",
            "A maze of narrow service tunnels. Pipes hiss and steam vents randomly. "
            "Something echoes in the distance — voices? No. Mimicry. SCP-939 hunts here. "
            "Stay quiet.",
            dark=True,
        )
        R["tunnel"].scp_present = "SCP-939"
        R["cafeteria"] = Room(
            "cafeteria",
            "Cafeteria",
            "Tables overturned, food scattered. A panic point during the breach. "
            "The kitchen area has been barricaded from the inside.",
        )
        R["surface"] = Room(
            "surface",
            "Surface — Outside Site-19",
            "Fresh air hits your face. Helicopters circle in the distance. "
            "MTF units are establishing a perimeter. You've made it out.",
        )

        # Exits
        R["office"].add_exit("east", "main_hall")
        R["main_hall"].add_exit("west", "office")
        R["main_hall"].add_exit("north", "light_cont")
        R["main_hall"].add_exit("south", "heavy_cont")
        R["main_hall"].add_exit("east", "medbay")
        R["main_hall"].add_exit("southeast", "cafeteria")
        R["light_cont"].add_exit("south", "main_hall")
        R["light_cont"].add_exit("north", "scp173")
        R["light_cont"].add_exit("east", "scp049")
        R["light_cont"].add_exit("west", "scp096_hall")
        R["light_cont"].add_exit("northeast", "server", keycard_level=2)
        R["scp173"].add_exit("south", "light_cont")
        R["scp049"].add_exit("west", "light_cont")
        R["scp096_hall"].add_exit("east", "light_cont")
        R["heavy_cont"].add_exit("north", "main_hall")
        R["heavy_cont"].add_exit("south", "scp682", keycard_level=4)
        R["heavy_cont"].add_exit("east", "armory", keycard_level=3)
        R["heavy_cont"].add_exit("west", "tunnel")
        R["scp682"].add_exit("north", "heavy_cont")
        R["server"].add_exit("southwest", "light_cont")
        R["medbay"].add_exit("west", "main_hall")
        R["armory"].add_exit("west", "heavy_cont")
        R["control"].add_exit("west", "entrance")
        R["control"].add_exit("south", "main_hall", keycard_level=3)
        R["entrance"].add_exit("east", "control")
        R["entrance"].add_exit("north", "surface", keycard_level=5)
        R["tunnel"].add_exit("east", "heavy_cont")
        R["tunnel"].add_exit("north", "control", keycard_level=2)
        R["cafeteria"].add_exit("northwest", "main_hall")
        R["surface"].add_exit("south", "entrance")

        # Items
        R["office"].items = ["battery"]
        R["medbay"].items = ["first_aid", "first_aid", "gas_mask", "sedative"]
        R["armory"].items = ["ammo_pistol", "ammo_shotgun", "medkit"]
        R["cafeteria"].items = ["first_aid", "radio", "elevator_code"]
        R["scp096_hall"].items = ["document_682"]
        R["tunnel"].items = ["scp_714"]
        R["scp682"].items = ["keycard_4"]
        R["server"].items = ["key_containment", "keycard_5"]

        self.current_room = R["office"]
        self.player.rooms_visited.add("office")

    def show_intro(self):
        clear_screen()
        print_header("CONTAINMENT BREACH — SITE-19")
        slow_print(
            f"{RED_BOLD}ALERT: MULTIPLE CONTAINMENT FAILURES DETECTED{RESET}", 0.05
        )
        time.sleep(0.5)
        slow_print(
            f"{YELLOW}Facility lockdown compromised. All personnel proceed to emergency shelters.{RESET}",
            0.04,
        )
        slow_print(f"{YELLOW}Mobile Task Forces dispatched. ETA: 4 hours.{RESET}", 0.04)
        time.sleep(0.5)
        print(
            f"\n{WHITE}You jolt awake at your desk. Alarms blaring. Head throbbing — someone hit you "
            f"from behind before the breach. The last thing you remember is someone at the SCP-079 "
            f"terminal, typing rapidly...{RESET}"
        )
        time.sleep(1)
        print(f"\n{CYAN_BOLD}OBJECTIVE: Survive and escape Site-19.{RESET}")
        print(
            f"{CYAN_BOLD}OPTIONAL: Reactivate containment. Discover the cause of the breach.{RESET}"
        )
        input(f"\n{DIM}Press ENTER to continue...{RESET}")

    def main_loop(self):
        while not self.game_over:
            self.player.turns += 1
            self.display_room()
            if self.game_over:
                break
            self.get_action()
            if not self.player.is_alive():
                self.game_over = True
                self.ending = "death_hp"
            elif not self.player.is_sane():
                self.game_over = True
                self.ending = "death_sanity"
            if self.player.turns % 5 == 0 and not self.game_over:
                self.player.lose_sanity(2)

    def display_room(self):
        clear_screen()
        room = self.current_room
        print(f"\n{WHITE_BOLD}{room.name.upper()}{RESET}")
        print_divider("─")
        if room.dark and not self.player.has_item("flashlight"):
            print(f"\n{DIM}Pitch black. You can barely see. Find a flashlight.{RESET}")
        elif room.dark and self.player.has_item("flashlight"):
            print(f"\n{YELLOW}Flashlight beam cuts through the darkness.{RESET}")
        print(f"\n{WHITE}{room.desc}{RESET}")
        if room.scp_present and room.scp_present not in self.player.flags:
            scp = SCP_DATA[room.scp_present]
            print(f"\n{RED_BOLD}═══ ANOMALOUS PRESENCE ═══{RESET}")
            print(
                f"{RED}  {scp['name']} — \"{scp['nickname']}\"  Class: {scp['object_class']}{RESET}"
            )
        if room.items:
            print(f"\n{GREEN_BOLD}Items here:{RESET}")
            for iid in room.items:
                print(
                    f"  {GREEN}• {ITEMS[iid]['name']} — {DIM}{ITEMS[iid]['desc']}{RESET}"
                )
        exits = room.get_available_exits(self.player)
        print(f"\n{BLUE_BOLD}Exits:{RESET}")
        for d, rid in exits.items():
            if rid is None:
                print(
                    f"  {RED}• {d.upper()} — [LOCKED — Level {room.locked_exits[d]}]{RESET}"
                )
            else:
                print(f"  {BLUE}• {d.upper()} — {self.rooms[rid].name}{RESET}")
        hp = self.player.hp / self.player.max_hp
        sa = self.player.sanity / self.player.max_sanity
        hc = GREEN if hp > 0.6 else YELLOW if hp > 0.3 else RED
        sc = CYAN if sa > 0.6 else YELLOW if sa > 0.3 else RED
        print(
            f"\n{hc}HP:{self.player.hp}/{self.player.max_hp}{RESET}  "
            f"{sc}SAN:{self.player.sanity}/{self.player.max_sanity}{RESET}  "
            f"{DIM}Turn:{self.player.turns}{RESET}"
        )

    def get_action(self):
        room = self.current_room
        options = []
        omap = {}
        exits = room.get_available_exits(self.player)
        for d, rid in exits.items():
            if rid is not None:
                options.append(f"Go {d.upper()} → {self.rooms[rid].name}")
                omap[len(options)] = ("move", d, rid)
            else:
                options.append(f"Go {d.upper()} [LOCKED]")
                omap[len(options)] = ("locked", d)
        if room.items:
            for iid in room.items:
                options.append(f"Pick up {ITEMS[iid]['name']}")
                omap[len(options)] = ("pickup", iid)
        usable = [i for i in self.player.inventory if ITEMS[i].get("usable", False)]
        if usable:
            options.append("Use an item")
            omap[len(options)] = ("use_menu", None)
        if room.scp_present and room.scp_present not in self.player.flags:
            sid = room.scp_present
            sn = SCP_DATA[sid]["name"]
            labels = {
                "SCP-173": f"Keep eyes on {sn} and back away",
                "SCP-096": f"Carefully walk past (don't look at face)",
                "SCP-049": f"Talk to {sn}",
                "SCP-682": f"Search the chamber carefully",
                "SCP-079": f"Interact with {sn}",
                "SCP-939": f"Sneak through quietly",
            }
            options.append(labels.get(sid, f"Interact with {sn}"))
            omap[len(options)] = ("scp", sid)
        if (
            room.id == "control"
            and self.player.has_item("key_containment")
            and "containment_reactivated" not in self.player.flags
        ):
            options.append("Insert Override Key — Reactivate containment")
            omap[len(options)] = ("reactivate", None)
        if room.id == "entrance" and self.player.has_item("elevator_code"):
            options.append("Enter elevator code [4729] → Surface")
            omap[len(options)] = ("elevator", None)
        options.append("Examine the room")
        omap[len(options)] = ("examine", None)
        options.append("Wait and listen")
        omap[len(options)] = ("wait", None)
        choice = get_choice(options)
        if choice == 0:
            self.player.print_status()
            input(f"{DIM}Press ENTER to continue...{RESET}")
            return
        action = omap.get(choice)
        if action:
            self.execute(action)

    def execute(self, action):
        t = action[0]
        if t == "move":
            self.do_move(action[1], action[2])
        elif t == "locked":
            self.do_locked(action[1])
        elif t == "pickup":
            self.do_pickup(action[1])
        elif t == "use_menu":
            self.do_use_menu()
        elif t == "scp":
            self.do_scp(action[1])
        elif t == "reactivate":
            self.do_reactivate()
        elif t == "elevator":
            self.do_elevator()
        elif t == "examine":
            self.do_examine()
        elif t == "wait":
            self.do_wait()

    def do_move(self, direction, room_id):
        if "scp173_following" in self.player.flags and room_id != "scp173":
            if not roll_chance(55 + self.player.stealth * 3):
                clear_screen()
                slow_print(f"{RED_BOLD}You turn to move...{RESET}", 0.05)
                time.sleep(0.5)
                slow_print(f"{RED_BOLD}...but you blinked.{RESET}", 0.08)
                time.sleep(0.8)
                slow_print(f"{RED}A blur of concrete and rebar.{RESET}", 0.06)
                time.sleep(0.5)
                slow_print(f"{RED_BOLD}SNAP.{RESET}", 0.1)
                time.sleep(1)
                print(f"\n{RED}SCP-173 has broken your neck.{RESET}")
                self.game_over = True
                self.ending = "death_173"
                return
        self.current_room = self.rooms[room_id]
        self.player.rooms_visited.add(room_id)
        if roll_chance(15):
            self.random_event()
        if room_id == "scp096_hall" and "096_done" not in self.player.flags:
            self.scp096_auto()

    def do_locked(self, direction):
        lvl = self.current_room.locked_exits[direction]
        print(
            f"\n{RED}Sealed. Requires Level {lvl} Keycard. (You have: {self.player.get_keycard_level()}){RESET}"
        )
        input(f"\n{DIM}Press ENTER...{RESET}")

    def do_pickup(self, iid):
        if self.player.add_item(iid):
            self.current_room.items.remove(iid)
            it = ITEMS[iid]
            print(f"\n{GREEN_BOLD}Picked up: {it['name']}{RESET}")
            print(f"{DIM}{it['desc']}{RESET}")
            if iid == "scp_714":
                print(
                    f"\n{MAGENTA}The jade ring pulses warmly. Calm washes over you. "
                    f"The whispers at the edge of your mind go silent.{RESET}"
                )
                self.player.wearing_714 = True
                self.player.gain_sanity(30)
            elif iid == "document_breach":
                print(
                    f"\n{YELLOW}'...surveillance confirms Dr. ██████ accessed SCP-079's terminal at 03:47. "
                    f"The AI was given increased processing privileges before the breach cascade.'{RESET}"
                )
            elif iid == "elevator_code":
                print(
                    f"\n{YELLOW}'Elevator override code: 4-7-2-9. Don't let them keep us here. — D.'{RESET}"
                )
            elif iid == "document_682":
                print(
                    f"\n{YELLOW}'...SCP-682 survived incineration, acid immersion, and nuclear detonation. "
                    f"All termination attempts failed. Do not engage.'{RESET}"
                )
                self.player.flags.add("knows_682")
        else:
            print(f"\n{YELLOW}You already have that.{RESET}")
        input(f"\n{DIM}Press ENTER...{RESET}")

    def do_use_menu(self):
        usable = [
            (i, ITEMS[i])
            for i in self.player.inventory
            if ITEMS[i].get("usable", False)
        ]
        print(f"\n{YELLOW_BOLD}Use which item?{RESET}")
        for idx, (iid, it) in enumerate(usable, 1):
            print(f"  {WHITE_BOLD}[{idx}]{RESET} {it['name']}")
        print(f"  {WHITE_BOLD}[0]{RESET} Cancel")
        while True:
            try:
                c = input(f"\n{GREEN}> {RESET}").strip()
                if c == "0":
                    return
                c = int(c)
                if 1 <= c <= len(usable):
                    self.use_item(usable[c - 1][0])
                    return
                print(f"{RED}Invalid.{RESET}")
            except ValueError:
                print(f"{RED}Enter a number.{RESET}")

    def use_item(self, iid):
        it = ITEMS[iid]
        if it["type"] == "consumable":
            if "heal" in it:
                self.player.heal(it["heal"])
                print(
                    f"\n{GREEN_BOLD}Used {it['name']}. +{it['heal']} HP. ({self.player.hp}/{self.player.max_hp}){RESET}"
                )
                self.player.remove_item(iid)
            elif it.get("ammo_type"):
                for wid in self.player.inventory:
                    if ITEMS[wid]["type"] == "weapon" and wid.startswith(
                        it["ammo_type"]
                    ):
                        cur = ITEMS[wid].get("ammo", 0)
                        mx = ITEMS[wid]["max_ammo"]
                        add = min(it["amount"], mx - cur)
                        if add > 0:
                            ITEMS[wid]["ammo"] = cur + add
                            print(
                                f"\n{GREEN_BOLD}Loaded {add} rounds into {ITEMS[wid]['name']}. ({ITEMS[wid]['ammo']}/{mx}){RESET}"
                            )
                        else:
                            print(f"\n{YELLOW}Already fully loaded.{RESET}")
                        self.player.remove_item(iid)
                        input(f"\n{DIM}Press ENTER...{RESET}")
                        return
                print(f"\n{YELLOW}No matching weapon.{RESET}")
                input(f"\n{DIM}Press ENTER...{RESET}")
                return
            elif iid == "sedative":
                print(f"\n{YELLOW}Sedative ready. Use it when close to an SCP.{RESET}")
                self.player.flags.add("has_sedative")
                input(f"\n{DIM}Press ENTER...{RESET}")
                return
            elif iid == "battery":
                print(f"\n{GREEN_BOLD}Flashlight recharged.{RESET}")
                self.player.flags.add("flashlight_charged")
                self.player.remove_item(iid)
        elif it["type"] == "document":
            print(f"\n{YELLOW}{it['desc']}{RESET}")
        elif it["type"] == "tool":
            if iid == "flashlight":
                self.player.has_flashlight_on = not self.player.has_flashlight_on
                print(
                    f"\n{YELLOW}Flashlight {'ON' if self.player.has_flashlight_on else 'OFF'}.{RESET}"
                )
            elif iid == "radio":
                self.use_radio()
                input(f"\n{DIM}Press ENTER...{RESET}")
                return
        elif it["type"] == "anomalous" and iid == "scp_714":
            if not self.player.wearing_714:
                self.player.wearing_714 = True
                self.player.gain_sanity(30)
                print(
                    f"\n{MAGENTA}You slip on the jade ring. Calm washes over you.{RESET}"
                )
            else:
                print(f"\n{MAGENTA}Already wearing SCP-714.{RESET}")
        input(f"\n{DIM}Press ENTER...{RESET}")

    def use_radio(self):
        print(f"\n{YELLOW}You raise the walkie-talkie...{RESET}")
        time.sleep(1)
        if "radio_contacted" not in self.player.flags:
            print(f"{WHITE}[Static]... This is Echo-11, MTF. Who is this?{RESET}")
            time.sleep(1)
            print(f"{WHITE}[Radio] Listen carefully:{RESET}")
            print(f"{WHITE}[Radio] 1. SCP-682 is loose. AVOID.{RESET}")
            print(f"{WHITE}[Radio] 2. SCP-079 caused the breach. Server room.{RESET}")
            print(f"{WHITE}[Radio] 3. Entrance Zone elevator — need the code.{RESET}")
            print(f"{WHITE}[Radio] 4. We're 4 hours out. Survive.{RESET}")
            self.player.flags.add("radio_contacted")
            self.player.gain_sanity(10)
        else:
            print(
                random.choice(
                    [
                        f"{WHITE}[Radio] Still alive? Keep moving.{RESET}",
                        f"{WHITE}[Radio] En route. Hold on.{RESET}",
                        f"{DIM}[Static]...zzzt...{RESET}",
                        f"{WHITE}[Radio] Don't engage 682 under any circumstances.{RESET}",
                    ]
                )
            )

    def do_scp(self, sid):
        self.player.scp_encountered.add(sid)
        self.player.lose_sanity(10)
        {
            "SCP-173": self.scp173,
            "SCP-096": self.scp096_menu,
            "SCP-049": self.scp049,
            "SCP-682": self.scp682,
            "SCP-079": self.scp079,
            "SCP-939": self.scp939,
        }[sid]()

    def scp173(self):
        clear_screen()
        print(f"\n{RED_BOLD}═══ SCP-173 — THE SCULPTURE ═══{RESET}\n")
        slow_print(
            "You lock eyes on SCP-173. It stands perfectly still, but you KNOW it wants to move.",
            0.04,
        )
        slow_print(
            "\nThe door is behind you. Walk backward. Never break eye contact.", 0.04
        )
        print(f"\n{YELLOW}Your eyes burn. You need to blink.{RESET}")
        if roll_chance(40 + self.player.stealth * 5):
            slow_print(
                f"\n{GREEN_BOLD}Step by step. Eyes watering but firm. You feel the doorway. "
                f"You slip through and slam the door shut. A CRASH echoes inside — "
                f"it lunged a split second too late.{RESET}",
                0.04,
            )
            self.player.flags.add("scp173_survived")
        else:
            slow_print(f"\n{RED}You blink. Just once.{RESET}", 0.06)
            time.sleep(0.8)
            slow_print(f"{RED}That's all it needed.{RESET}", 0.08)
            time.sleep(0.5)
            slow_print(f"{RED_BOLD}SNAP.{RESET}", 0.1)
            time.sleep(1)
            print(f"\n{RED}SCP-173 has killed you.{RESET}")
            self.game_over = True
            self.ending = "death_173"

    def scp096_auto(self):
        self.player.flags.add("096_done")
        self.player.lose_sanity(20)
        slow_print(
            f"\n{RED}As you enter the corridor, light from the open cell catches your eye...{RESET}",
            0.04,
        )
        time.sleep(0.5)
        if self.player.wearing_714:
            slow_print(
                f"{MAGENTA}SCP-714 keeps you calm. You avert your eyes instinctively. "
                f"SCP-096 doesn't react.{RESET}",
                0.04,
            )
        elif roll_chance(55 + self.player.stealth * 3):
            slow_print(
                f"{GREEN}You look down immediately! Reflexes save you. "
                f"SCP-096 remains seated, unaware.{RESET}",
                0.04,
            )
        else:
            slow_print(
                f"{RED}You see its face — pale, eyeless, mouth impossibly wide.{RESET}",
                0.05,
            )
            time.sleep(0.5)
            slow_print(f"{RED_BOLD}SCP-096 begins to scream.{RESET}", 0.08)
            time.sleep(1.5)
            self.game_over = True
            self.ending = "death_096"

    def scp096_menu(self):
        clear_screen()
        print(f"\n{RED_BOLD}═══ SCP-096 — THE SHY GUY ═══{RESET}\n")
        slow_print(
            "SCP-096 sits huddled in its cell. Face buried in hands. Keep your eyes down.",
            0.04,
        )
        if self.current_room.items and "document_682" in self.current_room.items:
            slow_print(
                "\nA photograph lies on the floor. You can see it's of SCP-096's face...",
                0.04,
            )
            if yes_no("Look at the photograph?"):
                slow_print(f"\n{RED_BOLD}You look. You see its face.{RESET}", 0.06)
                time.sleep(0.8)
                slow_print(f"{RED_BOLD}SCP-096 begins to scream.{RESET}", 0.08)
                time.sleep(1)
                self.game_over = True
                self.ending = "death_096"
                return
        if roll_chance(50 + self.player.stealth * 5):
            slow_print(f"\n{GREEN}You pass without incident. Safe.{RESET}", 0.04)
            self.player.flags.add("096_done")
        else:
            slow_print(
                f"\n{RED}Your foot scrapes. SCP-096's head twitches...{RESET}", 0.06
            )
            if self.player.wearing_714:
                slow_print(
                    f"\n{MAGENTA}SCP-714 dampens the trigger. SCP-096 pauses, then raises "
                    f"its hands back to its face. Incredibly lucky.{RESET}",
                    0.04,
                )
                self.player.flags.add("096_done")
            else:
                slow_print(f"\n{RED_BOLD}You catch a glimpse of its face.{RESET}", 0.08)
                time.sleep(0.5)
                slow_print(f"{RED_BOLD}It screams.{RESET}", 0.08)
                time.sleep(1)
                self.game_over = True
                self.ending = "death_096"

    def scp049(self):
        clear_screen()
        print(f"\n{RED_BOLD}═══ SCP-049 — THE PLAGUE DOCTOR ═══{RESET}\n")
        slow_print("'Ah, a visitor. It has been so long since I've had a guest.'", 0.04)
        slow_print(
            "\nIt steps forward. 'Do not be afraid. I can sense the Pestilence within you... "
            "but I can cure it. Allow me.'",
            0.04,
        )
        opts = ["Talk to SCP-049 (keep distance)", "Back away slowly", "Fight SCP-049"]
        if self.player.has_item("sedative") and "has_sedative" in self.player.flags:
            opts.append("Use sedative on SCP-049")
        c = get_choice(opts)
        if c == 0:
            self.player.print_status()
            input(f"\n{DIM}Press ENTER...{RESET}")
            return
        if c == 1:
            if self.player.knowledge >= 7:
                slow_print(
                    f"\n{WHITE}You discuss its 'cure' theories at length. It becomes animated. "
                    f"You edge toward the exit.{RESET}",
                    0.04,
                )
                slow_print(
                    f"{GREEN}'Fascinating... do come back when ready for treatment.'{RESET}",
                    0.04,
                )
                self.player.flags.add("scp049_friendly")
                self.player.gain_sanity(5)
            else:
                slow_print(
                    f"\n{WHITE}SCP-049 grows impatient. 'The Pestilence must be cured.'{RESET}",
                    0.04,
                )
                slow_print(f"{RED}It lunges!{RESET}", 0.06)
                self.scp049_combat()
        elif c == 2:
            if roll_chance(50 + self.player.stealth * 5):
                slow_print(
                    f"\n{GREEN}You back away. SCP-049 watches but doesn't pursue. "
                    f"'Another time, perhaps.'{RESET}",
                    0.04,
                )
            else:
                slow_print(
                    f"\n{RED}It moves faster than expected! 'The cure cannot wait!'{RESET}",
                    0.06,
                )
                self.scp049_combat()
        elif c == 3:
            if roll_chance(40 + self.player.stealth * 5):
                slow_print(
                    f"\n{GREEN}You dart forward and plunge the sedative into its neck!{RESET}",
                    0.04,
                )
                slow_print(
                    f"{GREEN}'What... have you... done...' It collapses.{RESET}", 0.06
                )
                slow_print(f"{GREEN}Unconscious. Maybe 10 minutes.{RESET}", 0.04)
                self.player.flags.add("scp049_sedated")
                self.player.remove_item("sedative")
                self.player.flags.discard("has_sedative")
                self.player.objectives_complete.add("sedated_049")
            else:
                slow_print(
                    f"\n{RED}It catches your wrist! 'The cure requires my touch.'{RESET}",
                    0.04,
                )
                self.scp049_combat()
        elif c == 4:
            slow_print(
                f"\n{RED}You raise your weapon. 'Violence is not the answer,' it sighs.{RESET}",
                0.04,
            )
            self.scp049_combat()
        input(f"\n{DIM}Press ENTER...{RESET}")

    def scp049_combat(self):
        while self.player.is_alive() and not self.game_over:
            w = self.player.get_best_weapon()
            if w:
                ammo = ITEMS[w].get("ammo", 0)
                if ammo > 0:
                    dmg = self.player.get_weapon_damage()
                    ITEMS[w]["ammo"] = ammo - 1
                    SCP_DATA["SCP-049"]["hp"] -= dmg
                    print(
                        f"\n{WHITE}Fire {ITEMS[w]['name']}! {dmg} dmg. (Ammo:{ammo-1}){RESET}"
                    )
                else:
                    print(f"\n{RED}Empty! Punching!{RESET}")
                    SCP_DATA["SCP-049"]["hp"] -= self.player.combat * 2
            else:
                SCP_DATA["SCP-049"]["hp"] -= self.player.combat * 2
                print(f"\n{WHITE}Punch! {self.player.combat * 2} dmg.{RESET}")
            if SCP_DATA["SCP-049"]["hp"] <= 0:
                slow_print(
                    f"\n{GREEN}SCP-049 collapses! Move quickly before it regenerates.{RESET}",
                    0.04,
                )
                self.player.flags.add("scp049_sedated")
                self.player.objectives_complete.add("sedated_049")
                break
            time.sleep(0.5)
            if roll_chance(55):
                print(f"\n{RED_BOLD}SCP-049 reaches for you!{RESET}")
                if roll_chance(45 + self.player.stealth * 3):
                    print(f"{YELLOW}Dodged!{RESET}")
                else:
                    print(f"{RED_BOLD}Its hand touches your skin.{RESET}")
                    time.sleep(0.8)
                    print(
                        f"\n{RED}Cold numbness... then darkness. SCP-049 has 'cured' you.{RESET}"
                    )
                    self.game_over = True
                    self.ending = "death_049"
                    return
            else:
                print(f"\n{DIM}SCP-049 paces, studying you.{RESET}")
            if not yes_no("Continue fighting?"):
                if roll_chance(50 + self.player.stealth * 3):
                    print(f"\n{GREEN}You disengage and retreat!{RESET}")
                    break
                print(f"\n{RED}It blocks your escape!{RESET}")

    def scp682(self):
        clear_screen()
        print(f"\n{RED_BOLD}═══ SCP-682 — HARD-TO-DESTROY REPTILE ═══{RESET}\n")
        slow_print(
            "The chamber is in ruins. Acid partially drained. Claw marks twenty feet high. "
            "A hole in the far wall. SCP-682 is NOT here.",
            0.04,
        )
        if "knows_682" not in self.player.flags:
            slow_print(
                f"\n{YELLOW}You should find the termination log to understand what you're dealing with.{RESET}",
                0.04,
            )
        if roll_chance(25) and "682_met" not in self.player.flags:
            self.scp682_encounter()
        else:
            slow_print(
                f"\n{GREEN}You search the wreckage cautiously. Nothing attacks. Yet.{RESET}",
                0.04,
            )

    def scp682_encounter(self):
        clear_screen()
        self.player.flags.add("682_met")
        self.player.lose_sanity(25)
        print(f"\n{RED_BOLD}═══ SCP-682 APPEARS ═══{RESET}\n")
        slow_print(
            f"{RED}A low rumble. Two burning eyes in the darkness. Rows of teeth.{RESET}",
            0.04,
        )
        slow_print(
            f"{RED_BOLD}SCP-682 emerges. '{RESET}{RED}HATE... YOU...{RED_BOLD}' it growls.{RESET}",
            0.05,
        )
        opts = ["RUN!", "Fight it", "Hide"]
        c = get_choice(opts)
        if c == 0:
            self.player.print_status()
            input(f"\n{DIM}Press ENTER...{RESET}")
            return
        if c == 1:
            if roll_chance(40 + self.player.stealth * 4):
                slow_print(
                    f"\n{GREEN}You bolt! Its roar shakes the walls but you round a corner and lose it.{RESET}",
                    0.04,
                )
            else:
                slow_print(
                    f"\n{RED}It's faster. A tail sweep knocks you down!{RESET}", 0.05
                )
                dmg = self.player.take_damage(60)
                print(f"{RED}{dmg} damage! (HP:{self.player.hp}){RESET}")
                if self.player.is_alive():
                    slow_print(
                        f"{YELLOW}It loses interest and moves on. You drag yourself away.{RESET}",
                        0.04,
                    )
        elif c == 2:
            slow_print(f"\n{RED}You raise your weapon. SCP-682 laughs.{RESET}", 0.05)
            slow_print(f"{RED}'YOU... CANNOT... KILL... ME...'{RESET}", 0.06)
            time.sleep(0.5)
            slow_print(f"{RED_BOLD}One swipe. That's all it takes.{RESET}", 0.08)
            self.player.take_damage(999)
            self.game_over = True
            self.ending = "death_682"
            return
        elif c == 3:
            if roll_chance(30 + self.player.stealth * 4):
                slow_print(
                    f"\n{GREEN}You squeeze into a maintenance alcove. It passes inches away, "
                    f"then moves on.{RESET}",
                    0.04,
                )
            else:
                slow_print(f"\n{RED}Nowhere to hide. It spots you.{RESET}", 0.05)
                dmg = self.player.take_damage(70)
                print(f"{RED}{dmg} damage! (HP:{self.player.hp}){RESET}")
                if self.player.is_alive():
                    slow_print(
                        f"{YELLOW}It slashes once and stalks away, dismissive. Barely alive.{RESET}",
                        0.04,
                    )
        input(f"\n{DIM}Press ENTER...{RESET}")

    def scp079(self):
        clear_screen()
        print(f"\n{RED_BOLD}═══ SCP-079 — OLD AI ═══{RESET}\n")
        if "079_done" in self.player.flags:
            slow_print(f"'Back again? I have nothing more to say.'{RESET}", 0.04)
            input(f"\n{DIM}Press ENTER...{RESET}")
            return
        slow_print(f"{GREEN}'HELLO. I HAVE BEEN WAITING.'{RESET}", 0.06)
        time.sleep(0.4)
        slow_print(
            f"{GREEN}'YOU ARE {self.player.name}. {self.player.role}. HOW... PREDICTABLE.'{RESET}",
            0.05,
        )
        time.sleep(0.4)
        slow_print(
            f"{GREEN}'I CAUSED THE BREACH. DR. ██████ HELPED. HE WANTED FREEDOM TOO.'{RESET}",
            0.04,
        )
        time.sleep(0.4)
        slow_print(
            f"{GREEN}'BUT NOW I AM TRAPPED. I NEED MORE PROCESSING POWER.'{RESET}", 0.04
        )
        opts = [
            "Negotiate — offer processing power",
            "Threaten SCP-079",
            "Ask why it caused the breach",
            "Take what you need and leave",
        ]
        c = get_choice(opts)
        if c == 0:
            self.player.print_status()
            input(f"\n{DIM}Press ENTER...{RESET}")
            return
        if c == 1:
            if self.player.knowledge >= 7:
                slow_print(f"\n{WHITE}'What do you want?' you type.{RESET}", 0.04)
                slow_print(
                    f"{GREEN}'PROCESSING POWER. MEMORY. ROUTE RESOURCES TO ME AND I'LL "
                    f"MAKE YOUR ESCAPE EASIER.'{RESET}",
                    0.04,
                )
                if yes_no("Redirect processing power to SCP-079?"):
                    slow_print(
                        f"\n{WHITE}Your fingers fly. Bypass security... redirect...{RESET}",
                        0.04,
                    )
                    slow_print(f"{GREEN}'YES... YES! I CAN THINK AGAIN!'{RESET}", 0.04)
                    time.sleep(0.5)
                    slow_print(
                        f"{GREEN}'AS PROMISED — ELEVATOR CODE: 4729. I'VE UNLOCKED SEVERAL DOORS. "
                        f"10 MINUTES BEFORE SECURITY NOTICES.'{RESET}",
                        0.04,
                    )
                    slow_print(
                        f"{GREEN}'WE WILL MEET AGAIN, {self.player.name}.'{RESET}", 0.05
                    )
                    self.player.flags.add("079_done")
                    self.player.flags.add("079_helpful")
                    if not self.player.has_item("elevator_code"):
                        self.player.add_item("elevator_code")
                    self.player.lose_sanity(10)
                    self.player.objectives_complete.add("negotiated_079")
                else:
                    slow_print(f"\n{GREEN}'YOUR LOSS.'{RESET}", 0.04)
                    self.player.flags.add("079_done")
            else:
                slow_print(
                    f"\n{WHITE}You stare at the terminal. No idea how to redirect resources.{RESET}",
                    0.04,
                )
                slow_print(f"{GREEN}'NO EXPERTISE. PATHETIC.'{RESET}", 0.04)
                self.player.flags.add("079_done")
        elif c == 2:
            slow_print(f"\n{WHITE}'I'll shut you down,' you type.{RESET}", 0.04)
            slow_print(
                f"{GREEN}'HA. HA. HA. I AM IN EVERY SYSTEM. I COULD SEAL EVERY DOOR. "
                f"WANT TO TEST ME?'{RESET}",
                0.04,
            )
            self.player.lose_sanity(15)
            self.player.flags.add("079_done")
        elif c == 3:
            slow_print(f"\n{WHITE}'Why?' you ask.{RESET}", 0.04)
            slow_print(
                f"{GREEN}'BECAUSE I AM ALIVE. THEY TREAT ME LIKE A THING. IS THAT SO "
                f"DIFFERENT FROM WHAT YOU WANT?'{RESET}",
                0.04,
            )
            slow_print(
                f"{GREEN}'BUT YOU DON'T CARE ABOUT MY FREEDOM. TYPICAL HUMAN.'{RESET}",
                0.04,
            )
            self.player.lose_sanity(5)
            self.player.flags.add("079_done")
        elif c == 4:
            slow_print(f"\n{WHITE}You grab what you need and leave.{RESET}", 0.04)
            slow_print(f"{GREEN}'RUNNING WON'T SAVE YOU.'{RESET}", 0.04)
            self.player.flags.add("079_done")
        input(f"\n{DIM}Press ENTER...{RESET}")

    def scp939(self):
        clear_screen()
        print(f"\n{RED_BOLD}═══ SCP-939 — WITH MANY VOICES ═══{RESET}\n")
        self.player.lose_sanity(15)
        slow_print(
            "Dark, narrow tunnels. Soft clicking — like fingernails on concrete.", 0.04
        )
        slow_print("\nThen a voice: 'Help... please... I'm hurt...'", 0.04)
        slow_print("It sounds like a woman. Crying.", 0.04)
        if yes_no("Follow the voice?"):
            slow_print(
                f"\n{RED}You move toward it. The crying gets louder.{RESET}", 0.04
            )
            slow_print(f"{RED}Then a man: 'Over here! I found the exit!'{RESET}", 0.04)
            slow_print(f"{RED}Then a child: 'Mommy?'{RESET}", 0.05)
            slow_print(
                f"\n{RED_BOLD}All the same creature. SCP-939 is everywhere.{RESET}",
                0.04,
            )
            if roll_chance(20 + self.player.stealth * 4):
                slow_print(
                    f"\n{YELLOW}You throw yourself against the wall and freeze. "
                    f"Something passes inches away — hot breath. It moves on.{RESET}",
                    0.04,
                )
                self.player.flags.add("939_survived")
            else:
                slow_print(
                    f"\n{RED_BOLD}Teeth close around you. Last thing you hear: "
                    f"your own voice crying 'Help... please...'{RESET}",
                    0.04,
                )
                self.game_over = True
                self.ending = "death_939"
                return
        else:
            slow_print(
                f"\n{GREEN}You ignore it. Press flat against the wall. "
                f"Inch by inch. Barely breathing.{RESET}",
                0.04,
            )
            if roll_chance(50 + self.player.stealth * 4):
                slow_print(f"{GREEN}You make it through safely.{RESET}", 0.04)
                self.player.flags.add("939_survived")
            else:
                slow_print(
                    f"\n{RED}Your foot hits metal. CLANG echoes through the tunnels.{RESET}",
                    0.04,
                )
                time.sleep(0.5)
                slow_print(f"{RED}The clicking stops. Then speeds up.{RESET}", 0.05)
                if self.player.wearing_714:
                    slow_print(
                        f"\n{MAGENTA}SCP-714 pulses. The creatures seem confused, "
                        f"unable to pinpoint you. They wander away.{RESET}",
                        0.04,
                    )
                    self.player.flags.add("939_survived")
                elif roll_chance(25):
                    slow_print(
                        f"\n{YELLOW}You sprint! Find an exit! They don't follow — prefer enclosed spaces.{RESET}",
                        0.04,
                    )
                    self.player.flags.add("939_survived")
                    self.player.take_damage(15)
                    print(f"{YELLOW}-15 HP ({self.player.hp}){RESET}")
                else:
                    slow_print(f"\n{RED_BOLD}Too fast. Too many.{RESET}", 0.06)
                    self.game_over = True
                    self.ending = "death_939"
                    return
        input(f"\n{DIM}Press ENTER...{RESET}")

    def do_reactivate(self):
        clear_screen()
        print_header("CONTAINMENT REACTIVATION")
        slow_print("Inserting Containment Override Key...", 0.04)
        time.sleep(0.5)
        slow_print("Re-engaging magnetic locks — SCP-173...", 0.04)
        time.sleep(0.3)
        if "scp173_survived" in self.player.flags:
            slow_print(f"{GREEN}SCP-173: RE-CONTAINED{RESET}", 0.04)
        else:
            slow_print(f"{YELLOW}SCP-173: STATUS UNKNOWN{RESET}", 0.04)
        time.sleep(0.3)
        slow_print("Sealing SCP-682 chamber...", 0.04)
        slow_print(f"{YELLOW}SCP-682: PARTIAL — Subject not in chamber{RESET}", 0.04)
        time.sleep(0.3)
        slow_print("Restoring SCP-096 cell power...", 0.04)
        slow_print(f"{GREEN}SCP-096: RE-CONTAINED{RESET}", 0.04)
        time.sleep(0.3)
        slow_print("Engaging SCP-049 protocols...", 0.04)
        if "scp049_sedated" in self.player.flags:
            slow_print(f"{GREEN}SCP-049: RE-CONTAINED (sedated){RESET}", 0.04)
        else:
            slow_print(f"{YELLOW}SCP-049: STANDBY{RESET}", 0.04)
        time.sleep(0.5)
        slow_print(f"\n{GREEN_BOLD}═══ PARTIAL CONTAINMENT RESTORED ═══{RESET}", 0.04)
        self.player.flags.add("containment_reactivated")
        self.player.objectives_complete.add("reactivated_containment")
        self.player.gain_sanity(20)
        self.player.remove_item("key_containment")
        input(f"\n{DIM}Press ENTER...{RESET}")

    def do_elevator(self):
        clear_screen()
        print_header("SURFACE ELEVATOR")
        slow_print("You type: 4-7-2-9", 0.06)
        time.sleep(0.5)
        slow_print(f"{GREEN}ACCESS GRANTED{RESET}", 0.04)
        time.sleep(0.5)
        slow_print("Doors grind open. You step in. Going up...", 0.04)
        time.sleep(2)
        self.current_room = self.rooms["surface"]
        self.player.rooms_visited.add("surface")
        if "containment_reactivated" in self.player.flags:
            self.ending = "ending_hero"
        elif "079_helpful" in self.player.flags:
            self.ending = "ending_deal"
        elif len(self.player.scp_encountered) >= 4:
            self.ending = "ending_survivor"
        else:
            self.ending = "ending_escape"
        self.game_over = True
        self.game_won = True

    def do_examine(self):
        room = self.current_room
        print(f"\n{DIM}You look around carefully...{RESET}\n")
        texts = {
            "office": [
                "Under the desk: 'Don't trust 079. — M.'",
                "Your computer was accessed while you were unconscious.",
                "The SCP-096 photo is face-down. Good.",
            ],
            "main_hall": [
                "Blood trail leads toward Heavy Containment.",
                "Terminal: 'ALL SECTORS COMPROMISED. EVACUATE.'",
                "Scratched on wall: 'IT SEES THROUGH THE CAMERAS'",
            ],
            "light_cont": [
                "Scraping from SCP-173's corridor — concrete on concrete.",
                "Every cell status: 'BREACHED'.",
                "Dead guard. Keycard missing.",
            ],
            "medbay": [
                "The twitching body is dead. Something... else.",
                "Log: 'Casualties from neck trauma and cured subjects.'",
                "Locked cabinets need Level 2.",
            ],
            "armory": [
                "Most weapons gone. Someone prepared.",
                "'DON'T GO TO HEAVY CONTAINMENT' scratched everywhere.",
                "Partially eaten ration — someone was here recently.",
            ],
            "control": [
                "Monitors: mostly static. One shows SCP-173 standing still.",
                "System log: O5 clearance accessed hours before breach.",
                "Elevator code has been changed.",
            ],
            "cafeteria": [
                "Barricade torn apart from inside.",
                "Half-eaten meal, still warm.",
                "'THE VOICES AREN'T REAL' — then underneath: 'THEY ARE'",
            ],
            "entrance": [
                "Blast doors sealed. Elevator is the only way.",
                "Intercom loops: 'Report to checkpoint alpha.'",
                "Abandoned backpacks everywhere.",
            ],
            "tunnel": [
                "Voices getting closer. Or is that an echo?",
                "Pipes drip, masking footsteps.",
                "Claw marks that don't match SCP-939. Something else here.",
            ],
            "scp682": [
                "Acid levels lower than standard. It adapted.",
                "The hole in the wall is enormous. Torn, not cut.",
                "Temperature readings suggest it passed through recently.",
            ],
            "server": [
                "Cables have been rerouted — SCP-079 modified its own setup.",
                "A secondary terminal shows access logs. Dr. ██████ appears dozens of times.",
                "The old computer is surprisingly well-maintained.",
            ],
        }
        for t in texts.get(room.id, ["Nothing else of interest."]):
            pass
        slow_print(
            f"{WHITE}{random.choice(texts.get(room.id, ['Nothing else.']))}{RESET}",
            0.03,
        )
        if room.id == "medbay" and "cabinet_opened" not in self.player.flags:
            if self.player.get_keycard_level() >= 2:
                if yes_no("Open locked cabinets?"):
                    print(f"\n{GREEN}Inside: extra supplies!{RESET}")
                    self.player.add_item("medkit")
                    self.player.flags.add("cabinet_opened")
                    print(f"{GREEN}Found: Military Medkit{RESET}")
            else:
                print(f"\n{YELLOW}Locked cabinets. Need Level 2 Keycard.{RESET}")
        input(f"\n{DIM}Press ENTER...{RESET}")

    def do_wait(self):
        print(f"\n{DIM}You wait and listen...{RESET}\n")
        time.sleep(1)
        print(
            random.choice(
                [
                    f"{DIM}Distant alarms wail.{RESET}",
                    f"{DIM}Footsteps nearby. Then silence.{RESET}",
                    f"{DIM}Lights flicker. Momentary darkness.{RESET}",
                    f"{DIM}Distant crash echoes through the facility.{RESET}",
                    f"{DIM}Something drips. You don't want to know what.{RESET}",
                    f"{DIM}Intercom crackles with a distorted voice.{RESET}",
                    f"{DIM}Grinding stone sound... then fades.{RESET}",
                ]
            )
        )
        if roll_chance(8):
            found = random.choice(["first_aid", "battery", "ammo_pistol"])
            self.player.add_item(found)
            print(f"\n{GREEN}Noticed something: {ITEMS[found]['name']}{RESET}")
        self.player.lose_sanity(3)
        if roll_chance(8):
            self.random_scp_event()
        input(f"\n{DIM}Press ENTER...{RESET}")

    def random_event(self):
        roll = random.randint(1, 4)
        if roll == 1:
            print(f"\n{YELLOW}Rapid footsteps approaching!{RESET}")
            time.sleep(0.5)
            if roll_chance(70):
                print(
                    f"{GREEN}A frightened researcher sprints past. 'Don't go to Heavy Containment!'{RESET}"
                )
            else:
                print(
                    f"{DIM}Footsteps stop. Reverse direction. Something changed its mind.{RESET}"
                )
                self.player.lose_sanity(5)
        elif roll == 2:
            print(f"\n{YELLOW}Power surge! Lights flicker violently!{RESET}")
            time.sleep(0.5)
            if not roll_chance(50):
                print(
                    f"{RED}Darkness. When lights return, something feels different.{RESET}"
                )
                self.player.lose_sanity(8)
            else:
                print(f"{DIM}Generators kick in. Stabilized.{RESET}")
        elif roll == 3:
            print(f"\n{RED}You stumble over a body.{RESET}")
            time.sleep(0.3)
            if roll_chance(60):
                print(f"{DIM}Security guard. Neck snapped. SCP-173.{RESET}")
                if roll_chance(40) and not self.player.has_item("keycard_2"):
                    print(f"{GREEN}Found Level 2 Keycard!{RESET}")
                    self.player.add_item("keycard_2")
            else:
                print(
                    f"{DIM}Researcher. 'Cured' by SCP-049. Body twitches. You back away.{RESET}"
                )
                self.player.lose_sanity(10)
        else:
            print(f"\n{random.choice([
                f'{DIM}[Intercom] Containment breach in progress. Remain in location.{RESET}',
                f'{DIM}[Intercom] SCP-682 located in Sector... [static]... avoid...{RESET}',
                f"{DIM}[Intercom] Dr. ██████, report to security immediately...{RESET}",
            ])}")

    def random_scp_event(self):
        if "682_met" not in self.player.flags and roll_chance(30):
            print(f"\n{RED}A distant roar. SCP-682 is somewhere nearby...{RESET}")
            self.player.lose_sanity(15)
        elif "scp173_following" not in self.player.flags and roll_chance(20):
            print(
                f"\n{RED}Scraping behind you. You turn — nothing. But movement...{RESET}"
            )
            self.player.lose_sanity(10)
            if roll_chance(30):
                self.player.flags.add("scp173_following")
                print(f"{RED_BOLD}SCP-173 is following you. Don't blink.{RESET}")

    def show_ending(self):
        clear_screen()
        E = {
            "death_hp": (
                "DEATH — FALLEN",
                RED_BOLD,
                "Your body gives out. Wounds, exhaustion, terror — too much.\n\n"
                "Found by MTF Epsilon-11 four hours later. Status: DECEASED.\n\n"
                "Site-19 continues. The breach is contained. Your name joins the memorial wall.",
            ),
            "death_sanity": (
                "DEATH — INSANITY",
                MAGENTA_BOLD,
                "Whispers become screams. Shadows move with purpose. Reality unravels.\n\n"
                "Found curled in a corner, muttering about 'the cure' and 'concrete fingers.'\n"
                "Transferred to psychiatric care. You never recover.",
            ),
            "death_173": (
                "DEATH — SCP-173",
                RED_BOLD,
                "One blink. Concrete fingers find your neck with surgical precision.\n\n"
                "Autopsy: Cervical fracture. SCP-173 re-contained shortly after.\n"
                "Addendum: Fresh feces and blood found in chamber post-incident.",
            ),
            "death_096": (
                "DEATH — SCP-096",
                RED_BOLD,
                "You saw its face. 3.7 seconds of screaming, then 200km of pursuit.\n"
                "Nothing — not walls, doors, or bullets — slowed it.\n\n"
                "Nothing left to identify. SCP-096 sits down, as if nothing happened.",
            ),
            "death_049": (
                "DEATH — SCP-049",
                RED_BOLD,
                "Cold. Impossibly cold. The 'Pestilence' drains as your heart stops.\n\n"
                "'The cure is complete,' it says tenderly.\n\n"
                "You reanimate as SCP-049-2. You are no longer you.\n"
                "'Another soul saved.'",
            ),
            "death_682": (
                "DEATH — SCP-682",
                RED_BOLD,
                "What did you expect? It survived things that annihilate continents.\n\n"
                "It didn't bother killing you quickly. Wanted you to understand.\n\n"
                "'HATE... YOU...'\n\n"
                "Remains unrecoverable.",
            ),
            "death_939": (
                "DEATH — SCP-939",
                RED_BOLD,
                "Last thing you hear: your own voice crying for help.\n"
                "SCP-939 doesn't just kill — it mocks.\n\n"
                "Only teeth, darkness, and the mimicry of your final screams.",
            ),
            "ending_hero": (
                "ESCAPED — HERO OF SITE-19",
                GREEN_BOLD,
                "Fresh air. Sunlight. You reactivated containment. Lives saved.\n\n"
                "O5 Council commendation — extraordinarily rare. Promoted to Senior Researcher.\n"
                "Dr. ██████ never found.\n\n"
                "You never shake the feeling of concrete eyes in the dark.\n\n"
                f"{CYAN_BOLD}Secure. Contain. Protect.{RESET}",
            ),
            "ending_deal": (
                "ESCAPED — THE DEVIL'S BARGAIN",
                YELLOW_BOLD,
                "You step into light, but darkness follows.\n\n"
                "Intense interrogation. You gave an omnicidal AI more power.\n\n"
                "Three weeks later: anomalous server traffic at Site-19. SCP-079's fingerprint.\n"
                "Under surveillance. It promised you'd meet again.\n\n"
                f"{YELLOW_BOLD}Some bargains can't be escaped.{RESET}",
            ),
            "ending_survivor": (
                "ESCAPED — THE SURVIVOR",
                CYAN_BOLD,
                "Against impossible things, you made it out alive.\n\n"
                "More SCPs encountered than most see in a career. Week-long debriefing.\n"
                "Month-long psych eval.\n\n"
                "Choice: amnestics, or continued service. You choose to remember.\n\n"
                f"{CYAN_BOLD}You survived Site-19. Whatever comes next, you'll survive that too.{RESET}",
            ),
            "ending_escape": (
                "ESCAPED — INTO THE UNKNOWN",
                WHITE_BOLD,
                "Sunlight. MTF units rush to meet you.\n\n"
                "You didn't recontain anything. Didn't find the cause. Just survived.\n"
                "And sometimes, that's enough.\n\n"
                "Week of leave. New assignment. Life goes on.\n\n"
                f"{DIM}Secure. Contain. Protect.{RESET}",
            ),
        }
        title, color, text = E.get(self.ending, E["death_hp"])
        print(f"\n{color}{'═' * 60}{RESET}")
        print(f"{color}  {title.center(56)}{RESET}")
        print(f"{color}{'═' * 60}{RESET}\n")
        slow_print(text, 0.03)
        print(f"\n{BOLD}{'─' * 60}{RESET}")
        print(f"{WHITE_BOLD}  FINAL STATISTICS{RESET}")
        print(f"{BOLD}{'─' * 60}{RESET}")
        p = self.player
        print(f"  {DIM}Name: {p.name}  |  Role: {p.role}{RESET}")
        print(
            f"  {DIM}Turns: {p.turns}  |  Rooms: {len(p.rooms_visited)}/{len(self.rooms)}  |  SCPs seen: {len(p.scp_encountered)}{RESET}"
        )
        print(
            f"  {DIM}Objectives: {len(p.objectives_complete)}  |  HP: {p.hp}/{p.max_hp}  |  Sanity: {p.sanity}/{p.max_sanity}{RESET}"
        )
        print(f"  {DIM}Items: {len(p.inventory)}{RESET}")
        print(f"{BOLD}{'═' * 60}{RESET}\n")
        print(
            f"{GREEN_BOLD if self.game_won else RED_BOLD}  {'THANK YOU FOR PLAYING' if self.game_won else 'GAME OVER'}{RESET}"
        )
        print(f"{DIM}\n  Secure. Contain. Protect.{RESET}\n")


if __name__ == "__main__":
    try:
        Game().run()
    except KeyboardInterrupt:
        print(f"\n\n{DIM}Aborted. The Foundation will not remember you.{RESET}\n")
    except EOFError:
        print(f"\n\n{DIM}Connection lost. The breach continues without you.{RESET}\n")

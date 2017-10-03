#!/usr/bin/env python3
import os
import curses
import time
import math
import random
import sys
import pickle

DEVMODE = 0
GAME_VERSION = 9
TIME_SCALE = 1
AUTOSAVE_TIME = 60
MODE_PLAY = 0
MODE_REBIRTH = 1
MODE_EVOLVE = 2
MODE_SHOP = 3
HEALTH_WIDTH = 20
UPGRADES = [
	[ 1,  "can_upgrade_damage_increase" , "Game is Hard I"     , "Allow Damage Increase to be upgraded"              , 250     , 0,    0,   0   ],
	[ 1,  "can_upgrade_attack_rate"     , "Game is Hard II"    , "Allow Attack Rate to be upgraded"                  , 1000    , 0,    0,   0   ],
	[ 1,  "can_rebirth"                 , "Game is Hard III"   , "Allow Rebirthing"                                  , 5000    , 0,    0,   0   ],
	[ 1,  "can_evolve"                  , "Game is Hard IV"    , "Allow Evolving"                                    , 1000000 , 0,    0,   0   ],
	[ 1,  "show_dps"                    , "Math is Hard I"     , "Show DPS"                                          , 20000   , 0,    1,   0   ],
	[ 1,  "show_dps_increase"           , "Math is Hard II"    , "Show DPS increase next to upgrades"                , 100000  , 0,    20,  0   ],
	[ 1,  "show_highest_level"          , "Memory is Hard I"   , "Show Highest Level"                                , 50000   , 1000, 0,   1   ],
	[ 1,  "show_highest_dps"            , "Memory is Hard II"  , "Show Highest DPS"                                  , 100000  , 2000, 5,   1   ],
	[ 1,  "show_elapsed"                , "Memory is Hard III" , "Show Elapsed Time"                                 , 150000  , 3000, 10,  5   ],
	[ 1,  "show_health_percent"         , "Reading is Hard I"  , "Show Health Percent"                               , 500000  , 0,    1,   0   ],
	[ 10, "reduce_upgrade_price"        , "Buying is Hard"     , "Reduce Upgrade Cost by 5% per rank"                , 1000000 , 0,    0,   10  ],
]

def get_max_sizes(data, padding):
	sizes = [padding] * (len(data[0])-1)

	for row in data:
		for index, value in enumerate(row[1:]):
			length = len(str(value))
			if length > sizes[index]:
				sizes[index] = length + padding

	return sizes

class Upgrade:

	def __init__(self, value, cost, cost_multiplier):
		self.value = value
		self.cost = cost
		self.cost_multiplier = cost_multiplier

	def buy(self, amount):
		self.cost = int(self.cost * self.cost_multiplier)
		self.value += amount

class State:

	def __init__(self, version):
		self.version = version
		self.base = {
			'level'                    : 1,
			'damage'                   : 1.0,
			'damage_increase'          : 1.0,
			'damage_increase_amount'   : 1.0,
			'attack_rate'              : 1.0,
			'attack_rate_increase'     : 0.1,
			'gold'                     : 0,
			'gold_multiplier'          : 1.0,
			'gold_multiplier_increase' : 0.05,
			'upgrade_price_growth'     : 1.2,
			'upgrade_price_multiplier' : 1.0,
			'rebirth_growth'           : 1.1,
			'rebirth_price_multiplier' : 1.0,
			'evolve_growth'            : 1.1,
			'evolve_price_multiplier'  : 1.0,
			'health_growth'            : 1.5,
			'health_multiplier'        : 1.0,
			'shop_growth'              : 10.0,
			'shop_multiplier'          : 1.0,
		}
		self.damage = Upgrade(self.base['damage'], 5, self.base['upgrade_price_growth'])
		self.damage_increase = Upgrade(self.base['damage_increase'], 50, self.base['upgrade_price_growth'])
		self.damage_increase_amount = Upgrade(self.base['damage_increase_amount'], 1000, self.base['upgrade_price_growth'])
		self.attack_rate = Upgrade(self.base['attack_rate'], 100, self.base['upgrade_price_growth'])
		self.attack_rate_increase = Upgrade(self.base['attack_rate_increase'], 10000, self.base['upgrade_price_growth'])
		self.gold = self.base['gold']
		self.gold_multiplier = self.base['gold_multiplier']
		self.gold_increase = Upgrade(self.base['gold_multiplier_increase'], 0, 0)
		self.level = self.base['level']
		self.health = 0
		self.max_health = 0
		self.health_multiplier = 1.0
		self.health_increase_exponent = self.base['health_growth']
		self.attack_timer = 0
		self.rebirth = Upgrade(0, 10000, self.base['rebirth_growth'])
		self.evolve = Upgrade(0, 10, self.base['evolve_growth'])
		self.highest = {
			'dps'       : 0,
			'level'     : 0,
			'rebirths'  : 0,
			'evolves'   : 0,
		}
		self.total = {
			'time'      : 0,
			'kills'     : 0,
			'gold'      : 0,
			'upgrades'  : 0,
			'rebirths'  : 0,
			'evolves'   : 0,
		}
		self.since = {
			'time'      : 0,
			'gold'      : 0,
			'upgrades'  : 0,
		}
		self.upgrades = {}
		self.builds = {}
		self.calc()

	# set values from base stats after rebirth/evolve
	def calc(self):
		self.damage.value = self.base['damage']
		self.damage_increase.value = self.base['damage_increase']
		self.attack_rate.value = self.base['attack_rate']

	# copy values after reset
	def copy(self, existing):
		self.base = existing.base
		self.upgrades = existing.upgrades
		self.highest = existing.highest
		self.total = existing.total
		self.builds = existing.builds

class Game:

	def __init__(self):
		self.save_file = "save.dat"
		self.version = GAME_VERSION
		self.done = 0
		self.message_size_y = 1
		self.screen = None
		self.state = None
		self.save_timer = 0
		self.max_fps = 150.0
		self.timestep = 1 / 100.0
		self.mode = MODE_PLAY
		self.rebirth_values = [ 1.0, 0.05 ]
		self.evolve_values = [ 10.0, 1.0 ]
		self.cursor = 0
		self.message = ""

		if sys.platform.startswith("win"):
			self.save_path = os.getenv("APPDATA") + "\\terminalheroes\\"
		else:
			self.save_path = os.getenv("HOME") + "/.local/share/terminalheroes/"

		if not os.path.exists(self.save_path):
			os.makedirs(self.save_path)

		self.screen = curses.initscr()
		self.screen.nodelay(1)
		(self.max_y, self.max_x) = self.screen.getmaxyx()

		try:
			self.win_game = curses.newwin(self.max_y-1, self.max_x, 0, 0)
			self.win_message = curses.newwin(self.message_size_y, self.max_x, int(self.max_y - self.message_size_y), 0)
		except:
			print("curses.newwin failed")
			curses.endwin()
			sys.exit(1)

		# set up colors
		curses.start_color()
		curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
		curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_RED)
		curses.init_pair(3, 8, curses.COLOR_BLACK)
		curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLACK)
		curses.init_pair(5, curses.COLOR_GREEN, curses.COLOR_RED)
		curses.curs_set(0)
		curses.noecho()

	def handle_input(self):

		# get key
		escape = False
		key_up = False
		key_down = False
		c = self.screen.getch()

		# handle multibyte keys
		if c == 27:
			nc = self.screen.getch()
			if nc == -1:
				escape = True
			else:
				c = self.screen.getch()
				if c == ord('A'):
					key_down = True
				elif c == ord('B'):
					key_up = True

				#self.message = "Escape Command: " + str(curses.keyname(c)) + " " + str(c) + " " + str(nc)

		# handle window resizes
		if c == curses.KEY_RESIZE:
			(self.max_y, self.max_x) = self.screen.getmaxyx()
			self.screen.erase()
			self.win_message.erase()
			if self.max_y > 1 and self.max_x > 0:
				self.win_game.resize(self.max_y-1, self.max_x)
				self.win_message.mvwin(int(self.max_y - self.message_size_y), 0)

		# handle based on mode
		if self.mode == MODE_PLAY:
			# ^X
			if c == 24:
				self.state = State(self.version)
				self.init_level()
				self.message = "New game!"
			elif c == ord('r'):
				if 'can_rebirth' in self.state.upgrades and self.state.gold >= self.state.rebirth.cost:
					self.mode = MODE_REBIRTH
					self.message = "[r] Cancel"
			elif c == ord('e'):
				if 'can_evolve' in self.state.upgrades and self.state.rebirth.value >= self.state.evolve.cost:
					self.mode = MODE_EVOLVE
					self.message = "[e] Cancel"
			elif c == ord('s'):
				self.mode = MODE_SHOP
				self.message = "[j] Down [k] Up [enter] Buy [s] Cancel"
			elif c == ord('u') or c == ord('1'):
				self.buy_upgrade(self.state.damage, self.state.damage_increase.value)
			elif c == ord('i') or c == ord('2'):
				if 'can_upgrade_damage_increase' in self.state.upgrades:
					self.buy_upgrade(self.state.damage_increase, self.state.damage_increase_amount.value)
			elif c == ord('o') or c == ord('3'):
				if 'can_upgrade_attack_rate' in self.state.upgrades:
					self.buy_upgrade(self.state.attack_rate, self.state.attack_rate_increase.value)
			elif c == ord('Q'):
				self.done = 1
			elif c == ord('q') or escape:
				self.save()
				self.done = 1
		elif self.mode == MODE_REBIRTH:
			confirm = False
			if c == ord('r') or escape:
				self.mode = MODE_PLAY
				self.message = ""
			elif c == ord('1'):
				self.state.damage_increase_amount.value += self.rebirth_values[0]
				confirm = True
			elif c == ord('2'):
				self.state.attack_rate_increase.value += self.rebirth_values[1]
				confirm = True

			if confirm:
				self.state.rebirth.buy(1)
				if self.state.rebirth.value > self.state.highest['rebirths']:
					self.state.highest['rebirths'] = self.state.rebirth.value
				old_state = self.state
				self.state = State(self.version)
				self.state.copy(old_state)
				self.state.rebirth = old_state.rebirth
				self.state.evolve = old_state.evolve
				self.state.damage_increase_amount.value = old_state.damage_increase_amount.value
				self.state.attack_rate_increase.value = old_state.attack_rate_increase.value
				self.state.calc()
				self.init_level()
				self.save()
				self.mode = MODE_PLAY

		elif self.mode == MODE_EVOLVE:
			confirm = False
			if c == ord('e') or escape:
				self.mode = MODE_PLAY
				self.message = ""
			elif c == ord('1'):
				self.state.base['damage'] += self.evolve_values[0]
				confirm = True
			elif c == ord('2'):
				self.state.base['attack_rate'] += self.evolve_values[1]
				confirm = True

			if confirm:
				self.state.evolve.buy(1)
				if self.state.evolve.value > self.state.highest['evolves']:
					self.state.highest['evolves'] = self.state.evolve.value
				old_state = self.state
				self.state = State(self.version)
				self.state.copy(old_state)
				self.state.evolve = old_state.evolve
				self.state.calc()
				self.init_level()
				self.save()
				self.mode = MODE_PLAY

		elif self.mode == MODE_SHOP:

			if c == ord('s') or escape:
				self.mode = MODE_PLAY
				self.message = ""
				self.cursor = 0
			elif c == 10:
				self.buy_shop_upgrade(self.cursor)
			elif key_up or c == ord('j'):
				self.cursor += 1
				if self.cursor > len(UPGRADES)-1:
					self.cursor = len(UPGRADES)-1
			elif key_down or c == ord('k'):
				self.cursor -= 1
				if self.cursor < 0:
					self.cursor = 0

		#if c != -1:
		#	self.message = "Command: " + str(curses.keyname(c)) + " " + str(c) + " " + str(nc)

	def start(self):
		self.state = State(self.version)
		self.state.version = self.version
		self.state.calc()
		self.load()
		if DEVMODE > 0:
			self.state.gold = 5000000000000000
			self.state.level = 5000
			self.state.rebirth.value = 100
			self.state.evolve.value = 100

		curses.doupdate()

		self.init_level()

	def draw_message(self):
		self.win_message.erase()

		try:
			self.win_message.addstr(0, 0, self.message[:self.max_x])
		except:
			pass

	def draw_table(self, y, template, data):
		for row in data:
			try:
				game.win_game.addstr(y, 0, template.format(*row[1:])[:self.max_x], row[0])
			except:
				pass

			y += 1
			if y >= self.max_y:
				return y

		return y

	def draw(self):
		state = game.state

		# clear screen
		self.draw_message()
		game.win_game.erase()

		if self.mode == MODE_PLAY:

			# precalculate stats
			dps = round(state.damage.value * state.attack_rate.value, 2)
			if dps > state.highest['dps']:
				state.highest['dps'] = dps

			gold = state.gold
			gold_multiplier = round(state.gold_multiplier, 2)
			rebirths = state.rebirth.value
			evolves = state.evolve.value
			damage = round(state.damage.value, 2)
			damage_increase = round(state.damage_increase.value, 2)
			damage_increase_amount = round(state.damage_increase_amount.value, 2)
			attack_rate = round(state.attack_rate.value, 2)
			attack_rate_increase = round(state.attack_rate_increase.value, 2)
			damage_cost = int(state.damage.cost * state.base['upgrade_price_multiplier'])
			damage_increase_cost = int(state.damage_increase.cost * state.base['upgrade_price_multiplier'])
			damage_increase_amount_cost = int(state.damage_increase_amount.cost * state.base['upgrade_price_multiplier'])
			attack_rate_cost = int(state.attack_rate.cost * state.base['upgrade_price_multiplier'])
			attack_rate_increase_cost = int(state.attack_rate_increase.cost * state.base['upgrade_price_multiplier'])

			# determine dps increase data
			dps_increase_header = ""
			dps_increase_damage = ""
			dps_increase_rate = ""
			if 'show_dps_increase' in state.upgrades:
				dps_increase_header = "DPS"
				dps_increase_damage = str(round(damage_increase * state.attack_rate.value, 2))
				dps_increase_rate = str(round(damage * attack_rate_increase, 2))

			# draw upgrades
			colors = [ curses.A_NORMAL, curses.A_BOLD ]
			data = []
			data.append([colors[1], 'Key', 'Upgrade', 'Base', 'Current', 'Increase', dps_increase_header, 'Cost'])
			data.append([colors[state.gold >= damage_cost], '[u]', 'Damage', str(state.base['damage']), str(damage), str(damage_increase), dps_increase_damage, str(damage_cost) + 'g'])
			if 'can_upgrade_damage_increase' in state.upgrades:
				data.append([colors[state.gold >= damage_increase_cost], '[i]', 'Damage Increase', str(state.base['damage_increase']), str(damage_increase), str(damage_increase_amount), '', str(damage_increase_cost) + 'g'])
			if 'can_upgrade_attack_rate' in state.upgrades:
				data.append([colors[state.gold >= attack_rate_cost], '[o]', 'Attack Rate', str(state.base['attack_rate']), str(attack_rate), str(attack_rate_increase), dps_increase_rate, str(attack_rate_cost) + 'g'])
			if 'can_rebirth' in state.upgrades:
				data.append([colors[state.gold >= state.rebirth.cost], '[r]', 'Rebirths', '', str(rebirths), str(1), '', str(state.rebirth.cost) + 'g'])
			if 'can_evolve' in state.upgrades:
				data.append([colors[state.rebirth.value >= state.evolve.cost], '[e]', 'Evolves', '', str(evolves), str(1), '', str(state.evolve.cost) + ' rebirths'])
			data.append([colors[0], '[s]', 'Shop', '', '', '', '', ''])

			sizes = get_max_sizes(data, 2)
			y = 0
			y = self.draw_table(y, "{0:%s} {1:%s} {2:%s} {3:%s} {4:%s} {5:%s} {6:%s}" % (*sizes,), data)
			y += 1

			# draw stats
			data = []
			data.append([curses.A_BOLD, 'Stats', 'Value'])
			if 'show_dps' in state.upgrades:
				data.append([curses.A_NORMAL, 'DPS', str(dps)])
			data.append([curses.A_NORMAL, 'Gold', str(gold)])
			if state.gold_multiplier != 1:
				data.append([curses.A_NORMAL, 'Gold Multiplier', str(gold_multiplier)])
			if 'show_highest_level' in state.upgrades:
				data.append([curses.A_NORMAL, 'Highest Level', str(state.highest['level'])])
			if 'show_highest_dps' in state.upgrades:
				data.append([curses.A_NORMAL, 'Highest DPS', str(state.highest['dps'])])
			if 'show_elapsed' in state.upgrades:
				data.append([curses.A_NORMAL, 'Elapsed Time', self.get_time(state.total['time'])])
			#data.append([curses.A_NORMAL, 'Time Since', self.get_time(state.since['time'])])
			#data.append([curses.A_NORMAL, 'Upgrades Since', str(state.since['upgrades'])])
			#data.append([curses.A_NORMAL, 'Gold Since', str(state.since['gold'])])
			#data.append([curses.A_NORMAL, 'Total Gold', str(state.total['gold'])])
			#data.append([curses.A_NORMAL, 'Total Upgrades', str(state.total['upgrades'])])
			#data.append([curses.A_NORMAL, 'Total Kills', str(state.total['kills'])])

			#data.append([curses.A_NORMAL, 'Highest Rebirths', str(state.highest['rebirths'])])
			#data.append([curses.A_NORMAL, 'Highest Evolves', str(state.highest['evolves'])])

			sizes = get_max_sizes(data, 2)
			y = self.draw_table(y, "{0:%s} {1:%s}" % (*sizes,), data)
			y += 1

			# draw health bar
			health_bar_header = ""
			health_bar_string = ""
			if 'show_health_percent' in state.upgrades:
				health_bars = int(HEALTH_WIDTH * (state.health / state.max_health))
				health_bar_header = "Percent"
				health_bar_string = ("#" * health_bars).ljust(HEALTH_WIDTH, "-")
				health_bar_string = "%s %.2f%%" % (health_bar_string, 100 * state.health / state.max_health)

			# draw enemy
			data = []
			data.append([curses.A_BOLD, 'Level', 'Health', 'Max Health', health_bar_header])
			data.append([curses.A_NORMAL, str(state.level), str(int(state.health)), str(int(state.max_health)), health_bar_string])

			sizes = get_max_sizes(data, 2)
			y = self.draw_table(y, "{0:%s} {1:%s} {2:%s} {3:%s}" % (*sizes,), data)

		elif self.mode == MODE_REBIRTH:

			try:
				y = 0
				game.win_game.addstr(y, 0, "Rebirth Options", curses.A_BOLD)

				y += 2
				game.win_game.addstr(y, 0, "[1] Upgrade Damage Increase Amount by " + str(self.rebirth_values[0]))

				y += 1
				game.win_game.addstr(y, 0, "[2] Upgrade Attack Rate Increase by " + str(self.rebirth_values[1]))

				y += 2
				game.win_game.addstr(y, 0, "[r] Cancel")
			except:
				pass

		elif self.mode == MODE_EVOLVE:

			try:
				y = 0
				game.win_game.addstr(y, 0, "Evolve Options", curses.A_BOLD)

				y += 2
				game.win_game.addstr(y, 0, "[1] Upgrade Base Damage by " + str(self.evolve_values[0]))

				y += 1
				game.win_game.addstr(y, 0, "[2] Upgrade Base Attack Rate by " + str(self.evolve_values[1]))

				y += 2
				game.win_game.addstr(y, 0, "[e] Cancel")
			except:
				pass

		elif self.mode == MODE_SHOP:

			try:
				y = 0
				game.win_game.addstr(y, 0, "Shop", curses.A_BOLD)

				y += 2
				game.win_game.addstr(y, 0, "You have " + str(state.gold) + " gold")
			except:
				pass

			y += 2

			# build upgrade list
			index = 0
			data = []
			data.append([curses.A_BOLD, "Rank", "Name", "Description", "Cost", "Level", "Rebirths", "Evolves"])
			for upgrade in UPGRADES:

				rank = 0
				if upgrade[1] in self.state.upgrades:
					rank = self.state.upgrades[upgrade[1]]

				cost = self.get_shop_cost(rank, index)

				color = 3
				if self.cursor == index:
					if upgrade[1] in self.state.upgrades:
						color = 5
					else:
						color = 2
				elif rank == upgrade[0]:
					color = 4
				elif self.can_buy_shop_item(rank, index):
					color = 1

				data.append([curses.color_pair(color), str(rank) + "/" + str(upgrade[0]), upgrade[2], upgrade[3], str(cost) + 'g', str(upgrade[5]), str(upgrade[6]), str(upgrade[7])])
				index += 1

			# draw upgrade table
			sizes = get_max_sizes(data, 2)
			y = self.draw_table(y, "{0:%s} {1:%s} {2:%s} {3:%s} {4:%s} {5:%s} {6:%s}" % (*sizes,), data)
			y += 1

		self.win_game.noutrefresh()
		self.win_message.noutrefresh()
		curses.doupdate()

	def get_shop_cost(self, rank, index):
		upgrade = UPGRADES[index]
		if rank >= upgrade[0]:
			rank = upgrade[0]-1

		return int(upgrade[4] * math.pow(self.state.base['shop_growth'], rank))

	def can_buy_shop_item(self, rank, index):
		upgrade = UPGRADES[index]
		if self.state.rebirth.value < upgrade[6]:
			return False

		if self.state.evolve.value < upgrade[7]:
			return False

		if self.state.level < upgrade[5]:
			return False

		return self.state.gold >= self.get_shop_cost(rank, index)

	def buy_shop_upgrade(self, index):
		upgrade = UPGRADES[index]

		# get existing upgrade
		has_upgrade = False
		rank = 0
		next_rank = 1
		if upgrade[1] in self.state.upgrades:
			has_upgrade = True
			rank = self.state.upgrades[upgrade[1]]
			next_rank = rank + 1

		# check buy conditions
		if rank < upgrade[0] and self.can_buy_shop_item(rank, index):
			self.state.upgrades[upgrade[1]] = next_rank
			self.state.gold -= self.get_shop_cost(rank, index)
			self.message = "Bought " + upgrade[1]
			if upgrade[1] == "reduce_upgrade_price":
				self.state.base['upgrade_price_multiplier'] = 1.0 - next_rank * 0.05

	def buy_upgrade(self, target, value):
		cost = int(target.cost * self.state.base['upgrade_price_multiplier'])
		if self.state.gold >= cost:
			self.state.gold -= cost
			self.state.total['upgrades'] += 1
			self.state.since['upgrades'] += 1
			target.buy(value)

	def get_time(self, time):
		if time < 60:
			return str(int(time)) + "s"
		elif time < 3600:
			return str(int(time / 60)) + "m"
		elif time < 86400:
			return str(int(time / 3600 % 24)) + "h" + str(int(time / 60 % 60)) + "m"
		else:
			return str(int(time / 86400)) + "d" + str(int(time / 3600 % 24)) + "h"

	def init_level(self):
		self.state.max_health = int(math.pow(self.state.level, self.state.health_increase_exponent) * self.state.health_multiplier)
		if self.state.health <= 0:
			self.state.health = self.state.max_health

	def update_health(self):
		if self.state.health <= 0:
			self.update_reward()
			self.state.level += 1
			if self.state.level > self.state.highest['level']:
				self.state.highest['level'] = self.state.level

			self.init_level()

	def get_reward(self, multiplier):
		return int(self.state.level * multiplier)

	def update_reward(self):
		total_reward = self.get_reward(self.state.gold_multiplier)

		self.message = "You earned " + str(total_reward) + " gold!"
		self.state.gold += total_reward
		self.state.total['gold'] += total_reward
		self.state.since['gold'] += total_reward
		self.state.total['kills'] += 1

	def update(self, frametime):
		self.state.total['time'] += frametime
		self.state.since['time'] += frametime

		# handle autosave
		self.save_timer += frametime
		if self.save_timer >= AUTOSAVE_TIME:
			self.save_timer = 0
			self.save()

		# make an attack
		period = 1.0 / self.state.attack_rate.value
		self.state.attack_timer += frametime
		while self.state.attack_timer >= period:
			self.state.attack_timer -= period
			self.state.health -= self.state.damage.value
			self.update_health()

	def load(self):
		try:
			with open(game.save_path + game.save_file, 'rb') as f:
				self.state = pickle.load(f)
		except:
			return

		# backup old save and create new save
		if self.state.version != self.version:
			os.rename(game.save_path + game.save_file, game.save_path + game.save_file + '.' + str(self.state.version))
			self.state = State(self.version)

	def save(self):
		with open(game.save_path + game.save_file, 'wb') as f:
			pickle.dump(self.state, f)

try:
	game = Game()
except Exception as e:
	curses.endwin()
	print(str(e))
	sys.exit(1)

timer = time.time()
accumulator = 0.0
game.start()
while not game.done:

	# get frame time
	frametime = (time.time() - timer)
	timer = time.time()

	# update input
	game.handle_input()

	# update game
	accumulator += frametime * TIME_SCALE
	while accumulator >= game.timestep:
		game.update(game.timestep)
		accumulator -= game.timestep

	# draw
	game.draw()

	# sleep
	if frametime > 0:
		extratime = 1.0 / game.max_fps - frametime
		if extratime > 0:
			time.sleep(extratime)

curses.endwin()

#!/usr/bin/env python3
import os
import curses
import time
import math
import random
import sys
import pickle

GAME_VERSION = 5
TIME_SCALE = 1
AUTOSAVE_TIME = 60
MODE_PLAY = 0
MODE_REBIRTH = 1
MODE_EVOLVE = 2
MODE_SHOP = 3
UPGRADES = [
	[ "show_dps", "Math is Hard I", "Show DPS", 20000, 0 ],
	[ "show_dps_increase", "Math is Hard II", "Show DPS increase next to upgrades", 100000, 0 ],
	[ "show_highest_level", "Memory is Hard I", "Show Highest Level", 50000, 1000 ],
	[ "show_highest_dps", "Memory is Hard II", "Show Highest DPS", 100000, 2000 ],
	[ "show_elapsed", "Memory is Hard III", "Show Elapsed Time", 150000, 3000 ],
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
		self.base_damage_increase = 0
		self.base_rate = 0
		self.damage = Upgrade(1.0, 5, 1.2)
		self.damage_increase = Upgrade(1.0, 50, 1.2)
		self.damage_increase_amount = 1.0
		self.rate = Upgrade(1.0, 100, 1.2)
		self.rate_increase = Upgrade(0.1, 0, 0)
		self.gold = 0
		self.gold_multiplier = 1.0
		self.gold_increase = Upgrade(0.05, 0, 0)
		self.level = 1
		self.health = 0
		self.max_health = 0
		self.health_multiplier = 1.0
		self.health_increase_exponent = 1.5
		self.attack_timer = 0
		self.rebirth = Upgrade(0, 10000, 1.1)
		self.evolve = Upgrade(0, 10, 1.1)
		self.highest = {
			'dps' : 0,
			'level' : 0,
			'time' : 0,
		}
		self.base = {}
		self.upgrades = {}

	# calculate base stats after upgrade/evolve
	def calc(self):
		self.damage.value += self.rebirth.value
		self.damage_increase.value += self.base_damage_increase
		self.rate.value += self.base_rate

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
		self.rebirth_values = [ 1.0, 0.05, 0.05 ]
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
				if self.state.gold >= self.state.rebirth.cost:
					self.mode = MODE_REBIRTH
			elif c == ord('e'):
				if self.state.rebirth.value >= self.state.evolve.cost:
					self.mode = MODE_EVOLVE
			elif c == ord('s'):
				self.mode = MODE_SHOP
				self.message = "[j] Down [k] Up [enter] Buy [s] Cancel"
			elif c == ord('u') or c == ord('1'):
				if self.state.gold >= self.state.damage.cost:
					self.state.gold -= self.state.damage.cost
					self.state.damage.buy(self.state.damage_increase.value)
			elif c == ord('i') or c == ord('2'):
				if self.state.gold >= self.state.damage_increase.cost:
					self.state.gold -= self.state.damage_increase.cost
					self.state.damage_increase.buy(self.state.damage_increase_amount)
			elif c == ord('o') or c == ord('3'):
				if self.state.gold >= self.state.rate.cost:
					self.state.gold -= self.state.rate.cost
					self.state.rate.buy(self.state.rate_increase.value)
			elif c == ord('q') or escape:
				self.save()
				self.done = 1
		elif self.mode == MODE_REBIRTH:
			confirm = False
			if c == ord('r') or escape:
				self.mode = MODE_PLAY
			elif c == ord('1'):
				self.state.damage_increase_amount += self.rebirth_values[0]
				confirm = True
			elif c == ord('2'):
				self.state.rate_increase.value += self.rebirth_values[1]
				confirm = True
			elif c == ord('3'):
				self.state.gold_multiplier += self.rebirth_values[2]
				confirm = True

			if confirm:
				self.state.rebirth.buy(1)
				old_state = self.state
				self.state = State(self.version)
				self.state.upgrades = old_state.upgrades
				self.state.highest = old_state.highest
				self.state.rebirth = old_state.rebirth
				self.state.evolve = old_state.evolve
				self.state.damage_increase_amount = old_state.damage_increase_amount
				self.state.rate_increase.value = old_state.rate_increase.value
				self.state.gold_multiplier = old_state.gold_multiplier
				self.state.base_damage_increase = old_state.base_damage_increase
				self.state.base_rate = old_state.base_rate
				self.state.calc()
				self.init_level()
				self.save()

		elif self.mode == MODE_EVOLVE:
			confirm = False
			if c == ord('e') or escape:
				self.mode = MODE_PLAY
			elif c == ord('1'):
				self.state.base_damage_increase += self.evolve_values[0]
				confirm = True
			elif c == ord('2'):
				self.state.base_rate += self.evolve_values[1]
				confirm = True

			if confirm:
				self.state.evolve.buy(1)
				old_state = self.state
				self.state = State(self.version)
				self.state.upgrades = old_state.upgrades
				self.state.highest = old_state.highest
				self.state.base_damage_increase = old_state.base_damage_increase
				self.state.base_rate = old_state.base_rate
				self.state.evolve = old_state.evolve
				self.state.calc()
				self.init_level()
				self.save()

		elif self.mode == MODE_SHOP:

			if c == ord('s') or escape:
				self.mode = MODE_PLAY
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
		#self.state.gold = 50000
		#self.state.rebirth.value = 100

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
			dps = round(state.damage.value * state.rate.value, 2)
			if dps > state.highest['dps']:
				state.highest['dps'] = dps

			gold = state.gold
			gold_multiplier = round(state.gold_multiplier, 2)
			rebirths = state.rebirth.value
			evolves = state.evolve.value
			damage = round(state.damage.value, 2)
			damage_increase = round(state.damage_increase.value, 2)
			damage_increase_amount = state.damage_increase_amount
			attack_rate = round(state.rate.value, 2)
			attack_rate_increase = round(state.rate_increase.value, 2)

			# determine dps increase data
			dps_increase_header = ""
			dps_increase_damage = ""
			dps_increase_rate = ""
			if 'show_dps_increase' in state.upgrades:
				dps_increase_header = "DPS"
				dps_increase_damage = str(round(damage_increase * state.rate.value, 2))
				dps_increase_rate = str(round(damage * attack_rate_increase, 2))

			# draw upgrades
			colors = [ curses.A_NORMAL, curses.A_BOLD ]
			data = []
			data.append([curses.A_BOLD, 'Key', 'Upgrade', 'Value', 'Increase', dps_increase_header, 'Cost'])
			data.append([colors[state.gold >= state.damage.cost], '[u]', 'Damage', str(damage), str(damage_increase), dps_increase_damage, str(state.damage.cost) + 'g'])
			data.append([colors[state.gold >= state.damage_increase.cost], '[i]', 'Damage Increase', str(damage_increase), str(damage_increase_amount), '', str(state.damage_increase.cost) + 'g'])
			data.append([colors[state.gold >= state.rate.cost], '[o]', 'Attack Rate', str(attack_rate), str(attack_rate_increase), dps_increase_rate, str(state.rate.cost) + 'g'])
			data.append([colors[state.gold >= state.rebirth.cost], '[r]', 'Rebirths', str(rebirths), str(1), '', str(state.rebirth.cost) + 'g'])
			data.append([colors[state.rebirth.value >= state.evolve.cost], '[e]', 'Evolves', str(evolves), str(1), '', str(state.evolve.cost) + ' rebirths'])
			data.append([1, '[s]', 'Shop', '', '', '', ''])

			sizes = get_max_sizes(data, 2)
			y = 0
			y = self.draw_table(y, "{0:%s} {1:%s} {2:%s} {3:%s} {4:%s} {5:%s}" % (*sizes,), data)
			y += 1

			# draw stats
			data = []
			data.append([curses.A_BOLD, 'Stats', 'Value'])
			if 'show_dps' in state.upgrades:
				data.append([curses.A_NORMAL, 'DPS', str(dps)])
			data.append([curses.A_NORMAL, 'Gold', str(gold)])
			data.append([curses.A_NORMAL, 'Gold Multiplier', str(gold_multiplier)])
			if 'show_highest_level' in state.upgrades:
				data.append([curses.A_NORMAL, 'Highest Level', str(state.highest['level'])])
			if 'show_highest_dps' in state.upgrades:
				data.append([curses.A_NORMAL, 'Highest DPS', str(state.highest['dps'])])
			if 'show_elapsed' in state.upgrades:
				data.append([curses.A_NORMAL, 'Elapsed Time', self.get_time(state.highest['time'])])

			sizes = get_max_sizes(data, 2)
			y = self.draw_table(y, "{0:%s} {1:%s}" % (*sizes,), data)
			y += 1

			# draw enemy
			data = []
			data.append([curses.A_BOLD, 'Level', 'Health', 'Max Health', '%'])
			data.append([curses.A_NORMAL, str(state.level), str(int(state.health)), str(int(state.max_health)), "%.2f " % (100 * state.health / state.max_health)])

#			# draw health bar
#			health_bars = int(HEALTH_WIDTH * (state.health / state.max_health))
#			string = ("#" * health_bars).ljust(HEALTH_WIDTH, "-")

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

				y += 1
				game.win_game.addstr(y, 0, "[3] Upgrade Gold Multiplier by " + str(self.rebirth_values[2]))

				y += 2
				game.win_game.addstr(y, 0, "[r] Cancel")
			except:
				pass

		elif self.mode == MODE_EVOLVE:

			try:
				y = 0
				game.win_game.addstr(y, 0, "Evolve Options", curses.A_BOLD)

				y += 2
				game.win_game.addstr(y, 0, "[1] Upgrade Base Damage Increase by " + str(self.evolve_values[0]))

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
			data.append([curses.A_BOLD, "Name", "Description", "Cost", "Level Required"])
			for upgrade in UPGRADES:

				color = 3
				if self.cursor == index:
					if upgrade[0] in self.state.upgrades:
						color = 5
					else:
						color = 2
				elif upgrade[0] in self.state.upgrades:
					color = 4
				elif self.can_buy_shop_item(index):
					color = 1

				data.append([curses.color_pair(color), upgrade[1], upgrade[2], str(upgrade[3]) + 'g', str(upgrade[4])])
				index += 1

			# draw upgrade table
			sizes = get_max_sizes(data, 2)
			y = self.draw_table(y, "{0:%s} {1:%s} {2:%s} {3:%s}" % (*sizes,), data)
			y += 1

		self.win_game.noutrefresh()
		self.win_message.noutrefresh()
		curses.doupdate()

	def can_buy_shop_item(self, index):
		upgrade = UPGRADES[index]
		if self.state.level < upgrade[4]:
			return False

		return self.state.gold >= upgrade[3]

	def buy_shop_upgrade(self, index):
		upgrade = UPGRADES[index]
		if upgrade[0] not in self.state.upgrades and self.can_buy_shop_item(index):
			self.state.upgrades[upgrade[0]] = 1
			self.state.gold -= upgrade[4]
			self.message = "Bought " + upgrade[0]

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
		self.mode = MODE_PLAY
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

	def update(self, frametime):
		self.state.highest['time'] += frametime
		self.save_timer += frametime

		if self.save_timer >= AUTOSAVE_TIME:
			self.save_timer = 0
			self.save()

		if self.mode == MODE_PLAY:
			self.state.attack_timer += frametime

			# make an attack
			period = 1.0 / self.state.rate.value
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

		if self.state.version != self.version:
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

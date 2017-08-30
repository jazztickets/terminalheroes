#!/usr/bin/env python3
import os
import curses
import time
import math
import random
import sys
import pickle

AUTOSAVE_TIME = 60
MODE_PLAY = 0
MODE_REBIRTH = 1
MODE_EVOLVE = 2

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
		self.highest_level = 1
		self.health = 0
		self.max_health = 0
		self.health_multiplier = 1.0
		self.health_increase_exponent = 1.5
		self.attack_timer = 0
		self.elapsed = 0.0
		self.rebirth = Upgrade(0, 10000, 1.1)
		self.evolve = Upgrade(0, 10, 1.1)

	# calculate base stats after upgrade/evolve
	def calc(self):
		self.damage.value += self.rebirth.value
		self.damage_increase.value += self.base_damage_increase
		self.rate.value += self.base_rate
		pass

class Game:

	def __init__(self):
		self.save_file = "save.dat"
		self.version = 2
		self.done = 0
		self.ready = 0
		self.size_x = 60
		self.size_y = 32
		self.message_size_y = 1
		self.health_width = 30
		self.screen = None
		self.state = None
		self.elapsed = 0
		self.save_timer = 0
		self.max_fps = 150.0
		self.timestep = 1 / 100.0
		self.mode = MODE_PLAY
		self.upgrade_values = [ 1.0, 0.05, 0.05 ]
		self.evolve_values = [ 10.0, 1.0 ]
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
			self.win_game = curses.newwin(self.size_y, self.size_x, int(self.max_y/2 - self.size_y/2), int(self.max_x/2 - self.size_x/2))
			self.win_command = curses.newwin(self.message_size_y, self.max_x)
			self.win_message = curses.newwin(self.message_size_y, self.max_x, int(self.max_y - self.message_size_y), 0)
		except:
			print("Increase your terminal window size")
			curses.endwin()
			sys.exit(1)

		# set up colors
		curses.start_color()
		curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
		curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_RED)
		curses.curs_set(0)
		curses.noecho()

	def handle_input(self):
		c = self.screen.getch()
		if c == curses.KEY_RESIZE:
			(self.max_y, self.max_x) = self.screen.getmaxyx()
			self.screen.erase()
			self.win_message.erase()
			self.win_message.mvwin(int(self.max_y - self.message_size_y), 0)

		if self.mode == MODE_PLAY:
			# ^X
			if c == 24:
				self.state = State(self.version)
				self.init_level()
				self.screen.erase()
				self.message = ""
			elif c == ord('r'):
				if self.state.gold >= self.state.rebirth.cost:
					self.mode = MODE_REBIRTH
			elif c == ord('e'):
				if self.state.rebirth.value >= self.state.evolve.cost:
					self.mode = MODE_EVOLVE
			elif c == ord('u'):
				if self.state.gold >= self.state.damage.cost:
					self.state.gold -= self.state.damage.cost
					self.state.damage.buy(self.state.damage_increase.value)
			elif c == ord('i'):
				if self.state.gold >= self.state.damage_increase.cost:
					self.state.gold -= self.state.damage_increase.cost
					self.state.damage_increase.buy(self.state.damage_increase_amount)
			elif c == ord('o'):
				if self.state.gold >= self.state.rate.cost:
					self.state.gold -= self.state.rate.cost
					self.state.rate.buy(self.state.rate_increase.value)
			elif c == ord('q'):
				self.save()
				self.done = 1
		elif self.mode == MODE_REBIRTH:
			confirm = False
			if c == ord('r'):
				self.mode = MODE_PLAY
			elif c == ord('1'):
				self.state.damage_increase_amount += self.upgrade_values[0]
				confirm = True
			elif c == ord('2'):
				self.state.rate_increase.value += self.upgrade_values[1]
				confirm = True
			elif c == ord('3'):
				self.state.gold_multiplier += self.upgrade_values[2]
				confirm = True

			if confirm:
				self.state.rebirth.buy(1)
				old_state = self.state
				self.state = State(self.version)
				self.state.elapsed = old_state.elapsed
				self.state.highest_level = old_state.highest_level
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
			if c == ord('e'):
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
				self.state.elapsed = old_state.elapsed
				self.state.highest_level = old_state.highest_level
				self.state.base_damage_increase = old_state.base_damage_increase
				self.state.base_rate = old_state.base_rate
				self.state.evolve = old_state.evolve
				self.state.calc()
				self.init_level()
				self.save()

		#if c != -1:
		#	self.win_command.addstr(1, 0, "Command: " + str(curses.keyname(c)) + "    ")
		#	self.win_command.addstr(1, 0, "Command: " + str(c))

	def start(self):
		self.state = State(self.version)
		self.state.version = self.version
		self.state.calc()
		self.load()
		#self.state.gold = 50000
		#self.state.rebirth.value = 100

		self.draw_keys()
		curses.doupdate()

		self.init_level()

	def draw_keys(self):
		self.win_command.erase()

		text = "q: quit ^X: new game u: upgrade damage i: upgrade damage increase o: upgrade attack rate r: rebirth e: evolve"
		try:
			self.win_command.addstr(0, 0, text[:self.max_x])
		except:
			pass

	def draw_message(self):
		self.win_message.erase()

		try:
			self.win_message.addstr(0, 0, self.message[:self.max_x])
		except:
			pass

	def draw(self):
		state = game.state

		# clear screen
		self.draw_keys()
		self.draw_message()
		game.win_game.erase()
		game.win_game.border(0, 0, 0, 0, 0, 0, 0, 0)

		if self.mode == MODE_PLAY:

			# draw level
			row = 2
			string = "Level: " + str(state.level)
			game.win_game.addstr(row, self.get_center(string), string)

			# draw health
			row += 1
			string = "Enemy Health: " + str(int(state.health)) + " / " + str(round(state.max_health, 2))
			game.win_game.addstr(row, self.get_center(string), string)

			# draw health bar
			row += 1
			health_percent = state.health / state.max_health
			health_bars = int(game.health_width * health_percent)
			string = ("#" * health_bars).ljust(game.health_width, "-")
			game.win_game.addstr(row, self.get_center(string), string)

			# draw dps
			row += 2
			string = "DPS: " + str(round(state.rate.value * state.damage.value, 2))
			game.win_game.addstr(row, self.get_center(string), string)

			# draw damage
			row += 2
			string = "Damage: " + str(round(state.damage.value, 2))
			game.win_game.addstr(row, self.get_center(string), string)

			# draw damage increase
			row += 1
			string = "Damage Increase: " + str(round(state.damage_increase.value, 2))
			game.win_game.addstr(row, self.get_center(string), string)

			# draw damage increase amount
			row += 1
			string = "Damage Increase Amount: " + str(state.damage_increase_amount)
			game.win_game.addstr(row, self.get_center(string), string)

			# draw attack rate
			row += 2
			string = "Attack Rate: " + str(round(state.rate.value, 2))
			game.win_game.addstr(row, self.get_center(string), string)

			# draw attack rate increase
			row += 1
			string = "Attack Rate Increase: " + str(round(state.rate_increase.value, 2))
			game.win_game.addstr(row, self.get_center(string), string)

			# draw gold multiplier
			row += 2
			string = "Gold Multiplier: " + str(round(state.gold_multiplier, 2))
			game.win_game.addstr(row, self.get_center(string), string)

			# draw gold
			row += 1
			string = "Gold: " + str(state.gold)
			game.win_game.addstr(row, self.get_center(string), string, curses.A_BOLD)

			# draw upgrade cost
			row += 2
			color = 1
			if state.gold >= state.damage.cost:
				color = 2
			string = "Upgrade Damage Cost: " + str(state.damage.cost)
			game.win_game.addstr(row, self.get_center(string), string, curses.color_pair(color))

			# draw upgrade damage increase cost
			row += 1
			color = 1
			if state.gold >= state.damage_increase.cost:
				color = 2
			string = "Upgrade Damage Increase Cost: " + str(state.damage_increase.cost)
			game.win_game.addstr(row, self.get_center(string), string, curses.color_pair(color))

			# draw upgrade attack rate cost
			row += 1
			color = 1
			if state.gold >= state.rate.cost:
				color = 2
			string = "Upgrade Attack Rate Cost: " + str(state.rate.cost)
			game.win_game.addstr(row, self.get_center(string), string, curses.color_pair(color))

			# draw rebirths
			row += 2
			string = "Rebirths: " + str(state.rebirth.value)
			game.win_game.addstr(row, self.get_center(string), string)

			# draw rebirth cost
			row += 1
			color = 1
			if state.gold >= state.rebirth.cost:
				color = 2
			string = "Rebirth Cost: " + str(state.rebirth.cost)
			game.win_game.addstr(row, self.get_center(string), string, curses.color_pair(color))

			# draw evolves
			row += 2
			string = "Evolves: " + str(state.evolve.value)
			game.win_game.addstr(row, self.get_center(string), string)

			# draw evolve cost
			row += 1
			color = 1
			if state.rebirth.value >= state.evolve.cost:
				color = 2
			string = "Next Evolve: " + str(state.evolve.cost) + " Rebirths"
			game.win_game.addstr(row, self.get_center(string), string, curses.color_pair(color))

			# draw elapsed time
			row += 2
			string = "Highest Level: " + str(state.highest_level)
			game.win_game.addstr(row, self.get_center(string), string)

			# draw elapsed time
			row += 1
			string = "Elapsed Time: " + self.get_time(state.elapsed)
			game.win_game.addstr(row, self.get_center(string), string)

		elif self.mode == MODE_REBIRTH:

			row = 2
			string = "Rebirth Options"
			game.win_game.addstr(row, self.get_center(string), string)

			row += 3
			string = "1: Upgrade Damage Increase Amount by " + str(self.upgrade_values[0])
			game.win_game.addstr(row, 2, string)

			row += 2
			string = "2: Upgrade Attack Rate Increase by " + str(self.upgrade_values[1])
			game.win_game.addstr(row, 2, string)

			row += 2
			string = "3: Upgrade Gold Multiplier by " + str(self.upgrade_values[2])
			game.win_game.addstr(row, 2, string)

			row += 2
			string = "r: Cancel"
			game.win_game.addstr(row, 2, string)

		elif self.mode == MODE_EVOLVE:

			row = 2
			string = "Evolve Options"
			game.win_game.addstr(row, self.get_center(string), string)

			row += 3
			string = "1: Upgrade Base Damage Increase by " + str(self.evolve_values[0])
			game.win_game.addstr(row, 2, string)

			row += 2
			string = "2: Upgrade Base Attack Rate by " + str(self.evolve_values[1])
			game.win_game.addstr(row, 2, string)

			row += 2
			string = "e: Cancel"
			game.win_game.addstr(row, 2, string)

		self.win_command.noutrefresh()
		self.win_game.noutrefresh()
		self.win_message.noutrefresh()
		curses.doupdate()

	def get_center(self, string):
		return int(game.size_x / 2 - len(string)/2) + 1

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
		self.state.health = self.state.max_health
		self.ready = 1

	def update_health(self):
		if self.state.health <= 0:
			self.update_reward()
			self.state.level += 1
			if self.state.level > self.state.highest_level:
				self.state.highest_level = self.state.level

			self.init_level()

	def get_reward(self, multiplier):
		return int(self.state.level * multiplier)

	def update_reward(self):

		total_reward = self.get_reward(self.state.gold_multiplier)

		self.message = "You earned " + str(total_reward) + " gold!"
		self.state.gold += total_reward

	def update(self, frametime):
		self.state.elapsed += frametime
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
	if game.ready:

		# get frame time
		frametime = (time.time() - timer)
		timer = time.time()

		# update input
		game.handle_input()

		# update game
		accumulator += frametime
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

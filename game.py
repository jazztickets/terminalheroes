#!/usr/bin/env python3
import curses
import threading
import time
import math
import random
import sys
import pickle

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
		self.dps = Upgrade(1.0, 10, 1.2)
		self.dps_increase = Upgrade(1.0, 100, 1.2)
		self.rebirth = Upgrade(0, 10000, 1.5)
		self.update_time = 1.0
		self.gold = 0
		self.gold_multiplier = 1
		self.level = 1
		self.health = 0
		self.max_health = 0
		self.health_multiplier = 3
		self.health_increase_exponent = 1.6
		self.dps_increase_amount = 1.0

class Game:

	def __init__(self):
		self.save_file = "save.dat"
		self.version = 1
		self.done = 0
		self.ready = 0
		self.size_x = 55
		self.size_y = 25
		self.message_size_y = 2
		self.health_width = 30
		self.screen = None
		self.state = None

		self.screen = curses.initscr()
		curses.start_color()
		curses.curs_set(0)
		curses.noecho()
		(self.max_y, self.max_x) = self.screen.getmaxyx()
		self.win_game = curses.newwin(self.size_y, self.size_x, int(self.max_y/2 - self.size_y/2), int(self.max_x/2 - self.size_x/2))
		self.win_command = curses.newwin(self.message_size_y, self.max_x)
		self.win_message = curses.newwin(self.message_size_y, self.max_x, int(self.max_y - self.message_size_y), 0)

		# set up colors
		curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
		curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_RED)

	def start(self):
		self.state = State(self.version)
		self.state.version = self.version
		self.load()

		self.win_command.addstr(0, 0, "q: quit ^X: new game u: upgrade dps i: upgrade dps increase r: rebirth")
		self.win_command.noutrefresh()
		curses.doupdate()

		self.init_level()
		while not self.done:
			c = self.win_command.getch()
			if c == curses.KEY_RESIZE:
				(max_y, max_x) = self.screen.getmaxyx()
			elif c == 10:
				pass
			# ^X
			elif c == 24:
				self.state = State(self.version)
				self.init_level()
			elif c == ord('r'):
				if self.state.gold >= self.state.rebirth.cost:
					self.state.rebirth.buy(1)
					dps_increase = self.state.dps_increase.value
					rebirth = self.state.rebirth
					self.state = State(self.version)
					self.state.dps_increase.value = dps_increase
					self.state.rebirth = rebirth
					self.init_level()
			elif c == ord('u'):
				if self.state.gold >= self.state.dps.cost:
					self.state.gold -= self.state.dps.cost
					self.state.dps.buy(self.state.dps_increase.value)
			elif c == ord('2'):
				self.state.update_time = 1.0
			elif c == ord('1'):
				self.state.update_time = 0.1
			elif c == ord('i'):
				if self.state.gold >= self.state.dps_increase.cost:
					self.state.gold -= self.state.dps_increase.cost
					self.state.dps_increase.buy(self.state.dps_increase_amount)
			elif c == ord('q'):
				self.save()
				self.done = 1
				break
			else:
				pass

			#if c != -1:
			#	self.win_command.addstr(1, 0, "Command: " + str(curses.keyname(c)) + "    ")
			#	self.win_command.addstr(1, 0, "Command: " + str(c))

			game.draw()
			self.win_command.noutrefresh()
			curses.doupdate()

	def draw(self):
		state = game.state
		game.win_game.erase()
		game.win_game.border(0, 0, 0, 0, 0, 0, 0, 0)

		# draw level
		row = 2
		string = "Level: " + str(state.level)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw health
		row += 1
		string = "Enemy Health: " + str(int(state.health)) + " / " + str(round(state.max_health, 2))
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw health bar
		row += 1
		health_percent = state.health / state.max_health
		health_bars = int(game.health_width * health_percent)
		string = ("#" * health_bars).ljust(game.health_width, "-")
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw dps
		row += 2
		string = "DPS: " + str(round(state.dps.value, 2))
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw dps increase
		row += 1
		string = "DPS Increase: " + str(state.dps_increase.value)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw dps increase amount
		row += 1
		string = "DPS Increase Amount: " + str(state.dps_increase_amount)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw gold multiplier
		row += 2
		string = "Gold Bonus: " + str(round(100 * state.gold_multiplier - 100)) + "%"
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw gold
		row += 1
		string = "Gold: " + str(state.gold)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string, curses.A_BOLD)

		# draw upgrade cost
		row += 2
		color = 1
		if state.gold >= state.dps.cost:
			color = 2
		string = "Upgrade DPS Cost: " + str(state.dps.cost)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string, curses.color_pair(color))

		# draw upgrade dps increase cost
		row += 1
		color = 1
		if state.gold >= state.dps_increase.cost:
			color = 2
		string = "Upgrade DPS Increase Cost: " + str(state.dps_increase.cost)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string, curses.color_pair(color))

		# draw rebirths
		row += 2
		string = "Rebirths: " + str(state.rebirth.value)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw rebirth cost
		row += 1
		color = 1
		if state.gold >= state.rebirth.cost:
			color = 2
		string = "Rebirth Cost: " + str(state.rebirth.cost)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string, curses.color_pair(color))

		self.win_game.noutrefresh()
		self.win_command.noutrefresh()
		self.win_message.noutrefresh()
		curses.doupdate()

	def set_status(self, text):
		self.win_message.erase()
		self.win_message.addstr(0, 0, text)

	def init_level(self):
		self.state.max_health = int(math.pow(self.state.level, self.state.health_increase_exponent) * self.state.health_multiplier)
		self.state.health = self.state.max_health
		self.ready = 1

	def update_health(self):
		if self.state.health <= 0:
			self.update_reward()
			self.state.level += 1
			self.init_level()

	def get_reward(self, multiplier):
		return int(self.state.level * multiplier)

	def update_reward(self):
		bonus = 0
		bonus_multiplier = 1
		if random.randint(0, 9) == 0:
			bonus_multiplier = 1.5
			bonus = 10

		total_reward = int((self.get_reward(bonus_multiplier) + bonus) * self.state.gold_multiplier)
		bonus_message = ""
		if bonus > 0:
			bonus_message = "BONUS! "

		self.set_status(bonus_message + "You earned " + str(total_reward) + " gold!")
		self.state.gold += total_reward

	def update(self):
		self.state.health -= self.state.dps.value
		self.update_health()

	def load(self):
		try:
			with open(game.save_file, 'rb') as f:
				self.state = pickle.load(f)
		except:
			return

		if self.state.version != self.version:
			self.state = State(self.version)

	def save(self):
		with open(game.save_file, 'wb') as f:
			pickle.dump(self.state, f)

def update_loop():

	while not game.done:
		if game.ready:
			game.update()
			game.draw()
			time.sleep(game.state.update_time)

game = Game()
update_thread = threading.Thread(target=update_loop)
update_thread.daemon = True
update_thread.start()
game.start()
game.done = 1
update_thread.join()

curses.endwin()

#!/usr/bin/env python3
import curses
import threading
import time
import random
import sys

class Game:
	done = 0
	ready = 0
	dps = 1
	gold = 0
	level = 1
	health = 0
	upgrade_cost = 10
	max_health = 0
	size_x = 55
	size_y = 25
	screen = None

	def __init__(self):
		self.screen = curses.initscr()
		curses.curs_set(0)
		curses.noecho()
		(self.max_y, self.max_x) = self.screen.getmaxyx()
		self.win_game = curses.newwin(self.size_y, self.size_x, int(self.max_y/2 - self.size_y/2), int(self.max_x/2 - self.size_x/2))
		self.win_command = curses.newwin(3, self.size_x)
	
	def start(self):
		
		self.win_command.addstr(0, 0, "q: quit u: upgrade")
		self.win_command.noutrefresh()
		curses.doupdate()

		self.init_level()
		while not self.done:
			c = self.win_command.getch()
			if c == curses.KEY_RESIZE:
				(max_y, max_x) = screen.getmaxyx()
			elif c == 10:
				pass
			elif c == ord('u'):
				if self.gold >= self.upgrade_cost:
					self.gold -= self.upgrade_cost
					self.upgrade_cost *= 1.2
					self.upgrade_cost = int(self.upgrade_cost)
					self.dps += 1
				pass
			elif c == ord('q'):
				self.done = 1
				break
			elif c != -1:
				self.win_command.addstr(1, 0, "Command: " + str(curses.keyname(c)) + "    ")

			game.draw()
			self.win_command.noutrefresh()
			curses.doupdate()

	def draw(self):
		game.win_game.erase()
		game.win_game.border(0, 0, 0, 0, 0, 0, 0, 0)

		# draw level
		row = 2
		string = "Level: " + str(game.level)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw health
		row += 1
		string = "Enemy Health: " + str(game.health)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw dps
		row += 2
		string = "DPS: " + str(game.dps)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw gold
		row += 1
		string = "Gold: " + str(game.gold)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw upgrade cost
		row += 1
		string = "Upgrade DPS Cost: " + str(game.upgrade_cost)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		self.win_game.noutrefresh()
		self.win_command.noutrefresh()
		curses.doupdate()

	def init_level(self):
		self.max_health = self.level * 5
		self.health = self.max_health
		self.ready = 1

	def update_health(self):
		if self.health <= 0:
			self.level += 1
			self.update_reward()
			self.init_level()

	def update_reward(self):
		bonus = 0
		if random.randint(0, 9) == 0:
			bonus = 10
			
		self.gold += self.level + bonus

	def update(self):
		self.health -= self.dps
		self.update_health()

game = Game()

def update_loop():

	while not game.done:
		if game.ready:
			game.update()
			game.draw()
			time.sleep(1)

update_thread = threading.Thread(target=update_loop)
update_thread.daemon = True
update_thread.start()
game.start()
game.done = 1
update_thread.join()


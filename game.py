#!/usr/bin/env python3
import curses
import threading
import time

class Game:
	done = 0
	dps = 1
	gold = 0
	level = 1
	health = 0
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
			elif c == ord('1'):
				pass
			elif c == ord('q'):
				self.done = 1
				break
			elif c != -1:
				self.win_command.addstr(1, 0, "Command: " + str(curses.keyname(c)) + "    ")

			self.win_command.noutrefresh()
			curses.doupdate()

	def draw(self):
		self.win_game.noutrefresh()
		self.win_command.noutrefresh()
		curses.doupdate()

	def init_level(self):
		self.max_health = self.level * 5
		self.health = self.max_health

	def update(self):
		self.health -= self.dps;
		if self.health <= 0:
			self.level += 1
			self.gold += self.level
			self.init_level()

game = Game()

def update_loop():

	while not game.done:
		game.win_game.erase()
		game.win_game.border(0, 0, 0, 0, 0, 0, 0, 0)
		row = 2

		# draw level
		string = "Level: " + str(game.level)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw health
		row += 1
		string = "Health: " + str(game.health)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw dps
		row += 1
		string = "DPS: " + str(game.dps)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		# draw gold
		row += 1
		string = "Gold: " + str(game.gold)
		game.win_game.addstr(row, int(game.size_x / 2 - len(string)/2) + 1, string)

		game.draw()
		game.update()
		time.sleep(1)

update_thread = threading.Thread(target=update_loop)
update_thread.daemon = True
update_thread.start()
game.start()
game.done = 1
update_thread.join()


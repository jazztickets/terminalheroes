#!/usr/bin/env python3
import os
import curses
import time
import math
import random
import sys
import pickle

DEVMODE = 0
GAME_VERSION = 13
TIME_SCALE = 1
AUTOSAVE_TIME = 60
SEQUENCE_INCREMENT = 5
PENALTIES_ALLOWED = 10
MODE_PLAY = 0
MODE_REBIRTH = 1
MODE_EVOLVE = 2
MODE_SHOP = 3
MODE_SEQUENCE = 4
HEALTH_WIDTH = 20

def get_max_sizes(data, padding):
	sizes = [padding] * (len(data[0])-1)

	for row in data:
		for index, value in enumerate(row[1:]):
			length = len(str(value))
			if length > sizes[index]:
				sizes[index] = length + padding

	return sizes

class Perk:

	def __init__(self, ranks, name, label, info, cost, level, rebirths, evolves, cost_multiplier):
		self.ranks = ranks
		self.name = name
		self.label = label
		self.info = info
		self.cost = cost
		self.level = level
		self.rebirths = rebirths
		self.evolves = evolves
		self.cost_multiplier = cost_multiplier

class Upgrade:

	def __init__(self, value, cost, cost_multiplier):
		self.value = value
		self.cost = cost
		self.cost_multiplier = cost_multiplier

	def buy(self, amount):
		self.cost = int(self.cost * self.cost_multiplier)
		self.value += amount

class Cost:

	def __init__(self, growth, multiplier):
		self.growth = growth
		self.multiplier = multiplier

class State:

	def __init__(self, version):
		self.version = version

		# base stats
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
		}

		# values associated with cost and increasing prices
		self.cost = {
			'upgrade'   : Cost(1.2, 1),
			'rebirth'   : Cost(1.1, 1),
			'evolve'    : Cost(1.1, 1),
			'health'    : Cost(1.5, 1),
		}

		# stats for records
		self.highest = {
			'dps'       : 0,
			'level'     : 0,
			'rebirth'   : 0,
			'evolve'    : 0,
		}

		# stats for running counts
		self.total = {
			'time'      : 0,
			'kill'      : 0,
			'gold'      : 0,
			'gold_lost' : 0,
			'upgrade'   : 0,
			'rebirth'   : 0,
			'evolve'    : 0,
		}

		# stats since last rebirth/evolve/reset
		self.since = {
			'time'      : 0,
			'gold'      : 0,
			'upgrade'   : 0,
		}

		# current sequences
		self.sequence = {
			'upgrade'   : 0,
			'rebirth'   : 0,
			'evolve'    : 0,
		}

		self.level = self.base['level']
		self.damage = Upgrade(self.base['damage'], 5, self.cost['upgrade'].growth)
		self.damage_increase = Upgrade(self.base['damage_increase'], 50, self.cost['upgrade'].growth)
		self.damage_increase_amount = Upgrade(self.base['damage_increase_amount'], 1000, self.cost['upgrade'].growth)
		self.attack_rate = Upgrade(self.base['attack_rate'], 100, self.cost['upgrade'].growth)
		self.attack_rate_increase = Upgrade(self.base['attack_rate_increase'], 10000, self.cost['upgrade'].growth)
		self.gold = self.base['gold']
		self.gold_multiplier = self.base['gold_multiplier']
		self.gold_increase = Upgrade(self.base['gold_multiplier_increase'], 0, 0)
		self.rebirth = Upgrade(0, 10000, self.cost['rebirth'].growth)
		self.evolve = Upgrade(0, 10, self.cost['evolve'].growth)
		self.perks = {}
		self.builds = {}
		self.health = 0
		self.max_health = 0
		self.attack_timer = 0
		self.time = time.time()
		self.calc()

	# set values from base stats after rebirth/evolve
	def calc(self):
		self.damage.value = self.base['damage']
		self.damage_increase.value = self.base['damage_increase']
		self.attack_rate.value = self.base['attack_rate']

	# copy values after reset
	def copy(self, existing):
		self.base = existing.base
		self.cost = existing.cost
		self.perks = existing.perks
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
		self.set_message("")

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

	# handle key presses
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
				self.save('.' + str(round(time.time()*1000)))
				self.state = State(self.version)
				self.init_level()
				self.set_message("New game!")
			elif c == ord('r'):
				if 'can_rebirth' in self.state.perks:
					self.mode = MODE_REBIRTH
					self.set_message("")
			elif c == ord('e'):
				if 'can_evolve' in self.state.perks:
					self.mode = MODE_EVOLVE
					self.set_message("")
			elif c == ord('s'):
				self.mode = MODE_SHOP
				self.set_message("[j] Down [k] Up [b] Buy [s] Cancel")
			elif c == ord('u') or c == ord('1'):
				if self.buy_upgrade(self.state.damage, self.state.damage_increase.value) == False:
					self.penalize()
			elif c == ord('i') or c == ord('2'):
				if 'can_upgrade_damage_increase' in self.state.perks:
					if self.buy_upgrade(self.state.damage_increase, self.state.damage_increase_amount.value) == False:
						self.penalize()
			elif c == ord('o') or c == ord('3'):
				if 'can_upgrade_attack_rate' in self.state.perks:
					if self.buy_upgrade(self.state.attack_rate, self.state.attack_rate_increase.value) == False:
						self.penalize()
			elif c == ord('Q'):
				self.done = 1
			elif c == ord('q') or escape:
				self.save()
				self.done = 1
		elif self.mode == MODE_REBIRTH:
			confirm = False
			if c == ord('r') or escape:
				self.mode = MODE_PLAY
				self.set_message("")
			elif c == ord('1'):
				self.buy_rebirth('1')
			elif c == ord('2'):
				self.buy_rebirth('2')
			elif c == ord('3'):
				self.set_sequence_mode('upgrade')
		elif self.mode == MODE_EVOLVE:
			confirm = False
			if c == ord('e') or escape:
				self.mode = MODE_PLAY
				self.set_message("")
			elif c == ord('1'):
				self.buy_evolve('1')
			elif c == ord('2'):
				self.buy_evolve('2')
			elif c == ord('3'):
				self.set_sequence_mode('rebirth')
		elif self.mode == MODE_SHOP:
			if c == ord('s') or escape:
				self.mode = MODE_PLAY
				self.set_message("")
				self.cursor = 0
			elif c == 10 or c == ord('b'):
				self.buy_perk(self.cursor)
			elif key_up or c == ord('j'):
				self.cursor += 1
				if self.cursor > len(PERKS)-1:
					self.cursor = len(PERKS)-1
			elif key_down or c == ord('k'):
				self.cursor -= 1
				if self.cursor < 0:
					self.cursor = 0
		elif self.mode == MODE_SEQUENCE:
			build = self.get_build(self.mode_build)
			if escape:
				self.mode = self.mode_previous
				self.set_message("")
				self.cursor = 0
				self.state.builds[self.mode_build] = self.old_sequence
				return
			elif c == 10:
				self.mode = self.mode_previous
				self.set_message("")
				self.cursor = 0
			elif c == ord('x') or c == 127:
				if len(build) > 0:
					build = build[:-1]

			if self.mode_build == 'upgrade':
				if c == ord('u'):
					build += 'u'
				elif c == ord('i'):
					build += 'i'
				elif c == ord('o'):
					build += 'o'
			elif self.mode_build == 'rebirth':
				if c == ord('1'):
					build += '1'
				elif c == ord('2'):
					build += '2'

			rank = self.state.perks['auto_' + self.mode_build]
			max_sequences = rank * SEQUENCE_INCREMENT
			self.state.builds[self.mode_build] = build[:max_sequences]

		if 0 and c != -1:
			self.set_message("Command: " + str(curses.keyname(c)) + " " + str(c))

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

		self.penalties = 0
		self.init_level()

	def set_sequence_mode(self, build):
		if 'auto_' + build not in self.state.perks:
			return

		self.mode_previous = self.mode
		self.mode = MODE_SEQUENCE
		message = ""
		if build == 'upgrade':
			message = "[u][i][o]"
		elif build == 'rebirth':
			message = "[1][2]"
		message += " Append Sequence [x] Erase [Enter] Confirm [Esc] Cancel"
		self.set_message(message)
		self.mode_build = build
		self.old_sequence = self.get_build(self.mode_build)

	def penalize(self):
		self.penalties += 1
		if self.penalties > PENALTIES_ALLOWED:
			gold_lost = math.ceil(self.state.gold * 0.1)
			if gold_lost > 0:
				self.state.total['gold_lost'] += gold_lost
				self.state.gold -= gold_lost
				self.set_message("PENALIZED! YOU LOST " + str(gold_lost) + " GOLD!", curses.color_pair(2))
		else:
			self.set_message("PENALTIES LEFT: " + str(PENALTIES_ALLOWED - self.penalties), curses.color_pair(2))

	def set_message(self, message, style=curses.A_NORMAL):
		self.message = message
		self.message_style = style

	def draw_message(self):
		self.win_message.erase()

		try:
			self.win_message.addstr(0, 0, self.message[:self.max_x], self.message_style)
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
			gold_lost = state.total['gold_lost']
			gold_multiplier = round(state.gold_multiplier, 2)
			rebirths = state.rebirth.value
			evolves = state.evolve.value
			damage = round(state.damage.value, 2)
			damage_increase = round(state.damage_increase.value, 2)
			damage_increase_amount = round(state.damage_increase_amount.value, 2)
			attack_rate = round(state.attack_rate.value, 2)
			attack_rate_increase = round(state.attack_rate_increase.value, 2)
			damage_cost = int(state.damage.cost * state.cost['upgrade'].multiplier)
			damage_increase_cost = int(state.damage_increase.cost * state.cost['upgrade'].multiplier)
			damage_increase_amount_cost = int(state.damage_increase_amount.cost * state.cost['upgrade'].multiplier)
			attack_rate_cost = int(state.attack_rate.cost * state.cost['upgrade'].multiplier)
			attack_rate_increase_cost = int(state.attack_rate_increase.cost * state.cost['upgrade'].multiplier)
			if 'auto_upgrade' in state.perks:
				auto_upgrade_max = self.state.perks['auto_upgrade'] * SEQUENCE_INCREMENT
				auto_upgrade_current = self.state.sequence['upgrade']
			if 'auto_rebirth' in state.perks:
				auto_rebirth_max = self.state.perks['auto_rebirth'] * SEQUENCE_INCREMENT
				auto_rebirth_current = self.state.sequence['rebirth']

			# determine dps increase data
			dps_increase_header = ""
			dps_increase_damage = ""
			dps_increase_rate = ""
			if 'show_dps_increase' in state.perks:
				dps_increase_header = "DPS"
				dps_increase_damage = str(round(damage_increase * state.attack_rate.value, 2))
				dps_increase_rate = str(round(damage * attack_rate_increase, 2))

			# draw perks
			colors = [ curses.A_NORMAL, curses.A_BOLD ]
			data = []
			data.append([colors[1], 'Key', 'Upgrade', 'Base', 'Current', 'Increase', dps_increase_header, 'Cost'])
			data.append([colors[state.gold >= damage_cost], '[u]', 'Damage', str(state.base['damage']), str(damage), str(damage_increase), dps_increase_damage, str(damage_cost) + 'g'])
			if 'can_upgrade_damage_increase' in state.perks:
				data.append([colors[state.gold >= damage_increase_cost], '[i]', 'Damage Increase', str(state.base['damage_increase']), str(damage_increase), str(damage_increase_amount), '', str(damage_increase_cost) + 'g'])
			if 'can_upgrade_attack_rate' in state.perks:
				data.append([colors[state.gold >= attack_rate_cost], '[o]', 'Attack Rate', str(state.base['attack_rate']), str(attack_rate), str(attack_rate_increase), dps_increase_rate, str(attack_rate_cost) + 'g'])
			if 'can_rebirth' in state.perks:
				data.append([colors[state.gold >= state.rebirth.cost], '[r]', 'Rebirths', '', str(rebirths), str(1), '', str(state.rebirth.cost) + 'g'])
			if 'can_evolve' in state.perks:
				data.append([colors[state.rebirth.value >= state.evolve.cost], '[e]', 'Evolves', '', str(evolves), str(1), '', str(state.evolve.cost) + ' rebirths'])
			data.append([colors[0], '[s]', 'Shop', '', '', '', '', ''])

			sizes = get_max_sizes(data, 2)
			y = 0
			y = self.draw_table(y, "{0:%s} {1:%s} {2:%s} {3:%s} {4:%s} {5:%s} {6:%s}" % (*sizes,), data)
			y += 1

			# draw stats
			data = []
			data.append([curses.A_BOLD, 'Stats', 'Value'])
			if 'show_dps' in state.perks:
				data.append([curses.A_NORMAL, 'DPS', str(dps)])
			data.append([curses.A_NORMAL, 'Gold', str(gold)])
			if gold_lost > 0:
				data.append([curses.A_NORMAL, 'Gold Lost', str(gold_lost)])
			if 'auto_upgrade' in state.perks:
				next_sequence = self.get_next_sequence('upgrade')
				if next_sequence != "":
					data.append([curses.A_NORMAL, 'Next Upgrade', "'" + next_sequence + "' (" + str(auto_upgrade_current) + " of " + str(auto_upgrade_max) + ")"])
			if 'auto_rebirth' in state.perks:
				next_sequence = self.get_next_sequence('rebirth')
				if next_sequence != "":
					data.append([curses.A_NORMAL, 'Next Rebirth', "'" + next_sequence + "' (" + str(auto_rebirth_current) + " of " + str(auto_rebirth_max) + ")"])
			if state.gold_multiplier != 1:
				data.append([curses.A_NORMAL, 'Gold Multiplier', str(gold_multiplier)])
			if 'show_highest_level' in state.perks:
				data.append([curses.A_NORMAL, 'Highest Level', str(state.highest['level'])])
			if 'show_highest_dps' in state.perks:
				data.append([curses.A_NORMAL, 'Highest DPS', str(state.highest['dps'])])
			if 'show_elapsed' in state.perks:
				data.append([curses.A_NORMAL, 'Elapsed Time', self.get_time(state.total['time'])])

			#data.append([curses.A_NORMAL, 'Time Since', self.get_time(state.since['time'])])
			#data.append([curses.A_NORMAL, 'Upgrades Since', str(state.since['upgrade'])])
			#data.append([curses.A_NORMAL, 'Gold Since', str(state.since['gold'])])
			#data.append([curses.A_NORMAL, 'Total Gold', str(state.total['gold'])])
			#data.append([curses.A_NORMAL, 'Total Upgrades', str(state.total['upgrade'])])
			#data.append([curses.A_NORMAL, 'Total Kills', str(state.total['kill'])])

			#data.append([curses.A_NORMAL, 'Highest Rebirths', str(state.highest['rebirth'])])
			#data.append([curses.A_NORMAL, 'Highest Evolves', str(state.highest['evolve'])])

			sizes = get_max_sizes(data, 2)
			y = self.draw_table(y, "{0:%s} {1:%s}" % (*sizes,), data)
			y += 1

			# draw health bar
			health_bar_header = ""
			health_bar_string = ""
			if 'show_health_percent' in state.perks:
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

				if self.state.gold >= self.state.rebirth.cost:
					y += 2
					game.win_game.addstr(y, 0, "[1] Upgrade Damage Increase Amount by " + str(self.rebirth_values[0]))

					y += 1
					game.win_game.addstr(y, 0, "[2] Upgrade Attack Rate Increase by " + str(self.rebirth_values[1]))

				if 'auto_upgrade' in state.perks:
					y += 1
					game.win_game.addstr(y, 0, "[3] Set Upgrade Sequence")

				y += 2
				game.win_game.addstr(y, 0, "[r] Cancel")
			except:
				pass

		elif self.mode == MODE_EVOLVE:

			try:
				y = 0
				game.win_game.addstr(y, 0, "Evolve Options", curses.A_BOLD)

				if self.state.rebirth.value >= self.state.evolve.cost:
					y += 2
					game.win_game.addstr(y, 0, "[1] Upgrade Base Damage by " + str(self.evolve_values[0]))

					y += 1
					game.win_game.addstr(y, 0, "[2] Upgrade Base Attack Rate by " + str(self.evolve_values[1]))

				if 'auto_rebirth' in state.perks:
					y += 1
					game.win_game.addstr(y, 0, "[3] Set Rebirth Sequence")

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
			for perk in PERKS:

				rank = 0
				if perk.name in self.state.perks:
					rank = self.state.perks[perk.name]

				cost = self.get_perk_cost(rank, index)

				color = 3
				if self.cursor == index:
					if perk.name in self.state.perks:
						color = 5
					else:
						color = 2
				elif rank == perk.ranks:
					color = 4
				elif self.can_buy_perk(rank, index):
					color = 1

				data.append([curses.color_pair(color), str(rank) + "/" + str(perk.ranks), perk.label, perk.info, str(cost) + 'g', str(perk.level), str(perk.rebirths), str(perk.evolves)])
				index += 1

			# draw upgrade table
			sizes = get_max_sizes(data, 2)
			y = self.draw_table(y, "{0:%s} {1:%s} {2:%s} {3:%s} {4:%s} {5:%s} {6:%s}" % (*sizes,), data)
			y += 1
		elif self.mode == MODE_SEQUENCE:
			build = self.get_build(self.mode_build)
			rank = self.state.perks['auto_' + self.mode_build]
			max_sequences = rank * SEQUENCE_INCREMENT

			try:
				y = 0
				game.win_game.addstr(y, 0, self.mode_build.title() + " Sequence", curses.A_BOLD)

				y += 2
				game.win_game.addstr(y, 0, build, curses.A_NORMAL)

				y += 2
				game.win_game.addstr(y, 0, "Used " + str(len(build)) + " of " + str(max_sequences), curses.A_BOLD)

			except:
				pass

		self.win_game.noutrefresh()
		self.win_message.noutrefresh()
		curses.doupdate()

	def get_next_sequence(self, name):
		build = self.get_build(name)
		sequence = self.state.sequence[name]
		if sequence < len(build):
			return build[sequence]

		return ""

	def get_build(self, build):
		if build not in self.state.builds:
			self.state.builds[build] = ""

		return self.state.builds[build]

	def get_perk_cost(self, rank, index):
		perk = PERKS[index]
		if rank >= perk.ranks:
			rank = perk.ranks-1

		return int(perk.cost * math.pow(perk.cost_multiplier, rank))

	def can_buy_perk(self, rank, index):
		perk = PERKS[index]
		if self.state.rebirth.value < perk.rebirths:
			return False

		if self.state.evolve.value < perk.evolves:
			return False

		if self.state.level < perk.level:
			return False

		return self.state.gold >= self.get_perk_cost(rank, index)

	def buy_perk(self, index):
		perk = PERKS[index]

		# get existing upgrade
		has_upgrade = False
		rank = 0
		next_rank = 1
		if perk.name in self.state.perks:
			has_upgrade = True
			rank = self.state.perks[perk.name]
			next_rank = rank + 1

		# check buy conditions
		if rank < perk.ranks and self.can_buy_perk(rank, index):
			self.state.perks[perk.name] = next_rank
			self.state.gold -= self.get_perk_cost(rank, index)
			self.set_message("Bought " + perk.name)
			if perk.name == "reduce_upgrade_price":
				self.state.cost['upgrade'].multiplier = 1.0 - next_rank * 0.05

	def buy_upgrade(self, target, value):
		cost = int(target.cost * self.state.cost['upgrade'].multiplier)
		if self.state.gold >= cost:
			self.state.gold -= cost
			self.state.total['upgrade'] += 1
			self.state.since['upgrade'] += 1
			target.buy(value)
			self.penalties = 0
			return True

		return False

	def buy_rebirth(self, option):
		if option == '' or self.state.gold < self.state.rebirth.cost:
			return False

		if option == '1':
			self.state.damage_increase_amount.value += self.rebirth_values[0]
		elif option == '2':
			self.state.attack_rate_increase.value += self.rebirth_values[1]

		self.state.rebirth.buy(1)
		if self.state.rebirth.value > self.state.highest['rebirth']:
			self.state.highest['rebirth'] = self.state.rebirth.value
		old_state = self.state
		self.state = State(self.version)
		self.state.copy(old_state)
		self.state.rebirth = old_state.rebirth
		self.state.evolve = old_state.evolve
		self.state.sequence['rebirth'] = old_state.sequence['rebirth'] + 1
		self.state.damage_increase_amount.value = old_state.damage_increase_amount.value
		self.state.attack_rate_increase.value = old_state.attack_rate_increase.value
		self.state.calc()
		self.init_level()
		self.penalties = 0
		self.save()
		self.mode = MODE_PLAY

		return True

	def buy_evolve(self, option):
		if option == '' or self.state.rebirth.value < self.state.evolve.cost:
			return False

		if option == '1':
			self.state.base['damage'] += self.evolve_values[0]
		elif option == '2':
			self.state.base['attack_rate'] += self.evolve_values[1]

		self.state.evolve.buy(1)
		if self.state.evolve.value > self.state.highest['evolve']:
			self.state.highest['evolve'] = self.state.evolve.value
		old_state = self.state
		self.state = State(self.version)
		self.state.copy(old_state)
		self.state.evolve = old_state.evolve
		self.state.sequence['evolve'] = old_state.sequence['evolve'] + 1
		self.state.calc()
		self.penalties = 0
		self.init_level()
		self.save()
		self.mode = MODE_PLAY

		return True

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
		self.state.max_health = int(math.pow(self.state.level, self.state.cost['health'].growth) * self.state.cost['health'].multiplier)
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

		self.set_message("You earned " + str(total_reward) + " gold!")
		self.state.gold += total_reward
		self.state.total['gold'] += total_reward
		self.state.since['gold'] += total_reward
		self.state.total['kill'] += 1

		# handle auto upgrades
		if self.mode == MODE_PLAY:
			command = self.get_next_sequence('upgrade')
			bought = False
			if command == 'u':
				bought = self.buy_upgrade(self.state.damage, self.state.damage_increase.value)
			elif command == 'i':
				if 'can_upgrade_damage_increase' in self.state.perks:
					bought = self.buy_upgrade(self.state.damage_increase, self.state.damage_increase_amount.value)
			elif command == 'o':
				if 'can_upgrade_attack_rate' in self.state.perks:
					bought = self.buy_upgrade(self.state.attack_rate, self.state.attack_rate_increase.value)

			if bought:
				self.state.sequence['upgrade'] += 1

			# handle auto rebirths
			command = self.get_next_sequence('rebirth')
			bought = self.buy_rebirth(command)

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

	def save(self, suffix=''):
		self.state.time = time.time()
		with open(game.save_path + game.save_file + suffix, 'wb') as f:
			pickle.dump(self.state, f)

PERKS = [
	Perk( 1,   "can_upgrade_damage_increase" , "Game is Hard I"     , "Allow Damage Increase to be upgraded"                         , 250       , 0,    0,   0,   0   ),
	Perk( 1,   "can_upgrade_attack_rate"     , "Game is Hard II"    , "Allow Attack Rate to be upgraded"                             , 2000      , 0,    0,   0,   0   ),
	Perk( 1,   "can_rebirth"                 , "Game is Hard III"   , "Allow Rebirthing"                                             , 20000     , 0,    0,   0,   0   ),
	Perk( 1,   "can_evolve"                  , "Game is Hard IV"    , "Allow Evolving"                                               , 1000000   , 0,    0,   0,   0   ),
	Perk( 1,   "show_dps"                    , "Math is Hard I"     , "Show DPS"                                                     , 20000     , 0,    1,   0,   0   ),
	Perk( 1,   "show_dps_increase"           , "Math is Hard II"    , "Show DPS increase next to upgrades"                           , 100000    , 0,    20,  0,   0   ),
	Perk( 1,   "show_highest_level"          , "Memory is Hard I"   , "Show Highest Level"                                           , 50000     , 1000, 0,   1,   0   ),
	Perk( 1,   "show_highest_dps"            , "Memory is Hard II"  , "Show Highest DPS"                                             , 100000    , 2000, 5,   1,   0   ),
	Perk( 1,   "show_elapsed"                , "Memory is Hard III" , "Show Elapsed Time"                                            , 150000    , 3000, 10,  5,   0   ),
	Perk( 1,   "show_health_percent"         , "Reading is Hard I"  , "Show Health Percent"                                          , 500000    , 0,    1,   0,   0   ),
	Perk( 10,  "reduce_upgrade_price"        , "Buying is Hard"     , "Reduce Upgrade Cost by 5% per Rank"                           , 1000000   , 0,    0,   10,  10  ),
	Perk( 100, "auto_upgrade"                , "Upgrading is Hard"  , "Set an Upgrade Sequence on Rebirth"                           , 1000000   , 0,    0,   5,   2   ),
	Perk( 100, "auto_rebirth"                , "Rebirthing is Hard" , "Set a Rebirth Sequence on Evolve"                             , 10000000  , 0,    0,   10,  2   ),
]

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

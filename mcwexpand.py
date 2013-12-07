#!/usr/bin/env python2

import argparse
import os
from os.path import join, dirname
import random
import shutil
import string
import subprocess
import time

from nbt import nbt


# server generates at the start 25x25 chunks
# we use a small tolerance
ITERATION_BLOCK_OFFSET = 24 * 16

# add an option for this later
LOGFILE = join(dirname(__file__), "mcwexpand.log")

def random_string(length, chars=string.ascii_lowercase):
    return "".join([ random.choice(chars) for i in xrange(length)])

def copy_template(template, template_to, template_vars={}):
    to = open(template_to, "w")
    data = open(template).read()
    for line in data.split("\n"):
        if line.startswith("#"):
            print >> to, line
            continue
        split = line.split("=")
        if len(split) != 2:
            print >> to, line
            continue
        key, value = split
        key, value = key.strip(), value.strip()
        if key in template_vars:
            value = template_vars[key]
        print >> to, "%s=%s" % (key, value)
    to.close()

def iterate_bounds(bounds):
    minx, minz, maxx, maxz = bounds
    for dx in range(minx, maxx+1):
        for dz in range(minz, maxz+1):
            if (dx, dz) == (0, 0):
                continue
            yield dx, dz

class Server(object):
    def __init__(self, serverdir, worlddir, seed=None):
        self.serverdir = serverdir
        
        self.worlddir = worlddir
        self.seed = seed
    
    def create_serverdir(self, templatedir):
        os.mkdir(self.serverdir)
        shutil.copy(join(templatedir, "server.properties.tpl"), join(self.serverdir, "server.properties.tpl"))
        shutil.copy(join(templatedir, "minecraft_server.jar"), join(self.serverdir, "minecraft_server.jar"))
    
        template = join(self.serverdir, "server.properties.tpl")
        template_to = join(self.serverdir, "server.properties")
        template_vars = {
            "level-name" : os.path.relpath(self.worlddir, self.serverdir),
        }
        if self.seed is not None:
            template_vars["level-seed"] = self.seed
        copy_template(template, template_to, template_vars)
    
    def run(self, verbose=False):
        kwargs = {
             "cwd" : self.serverdir, #join(dirname(__file__), "server"), 
             "stdout" : subprocess.PIPE, 
             "stderr" : subprocess.PIPE, 
             "stdin" : subprocess.PIPE
        }
        
        log = open(LOGFILE, "a")
        p = subprocess.Popen(["java", "-jar", "minecraft_server.jar", "nogui"], **kwargs)
        p.stdin.write("stop\n")
        while 42:
            line = p.stdout.readline()
            if not line:
                break
            line = line.rstrip()
            print >> log, line
            if verbose:
                print line
        print >> log, ""
        log.close()

def expand_world(server, include, exclude=None, verbose=False):    
    print "Running server for the first time..."
    server.run(verbose)
    
    leveldat_path = join(server.worlddir, "level.dat")
    # create a backup of the level.dat
    shutil.copy(leveldat_path, leveldat_path + ".mcexpandbak")
    
    leveldat = nbt.NBTFile(filename=leveldat_path)
    spawn_x = leveldat["Data"]["SpawnX"].value
    spawn_z = leveldat["Data"]["SpawnZ"].value
    print "Found original spawn point: %d:%d" % (spawn_x, spawn_z)
    
    positions = set(iterate_bounds(include))
    if exclude is not None: 
        positions -= set(iterate_bounds(exclude))
    positions = sorted(list(positions))
    print "Doing %d iterations..." % len(positions)
    i = 0
    for dx, dz in positions:
        i += 1
        
        print "[%d/%d] Generating %d, %d ..." % (i, len(positions), dx, dz)
        leveldat["Data"]["SpawnX"].value = spawn_x + dx*ITERATION_BLOCK_OFFSET
        leveldat["Data"]["SpawnZ"].value = spawn_z + dz*ITERATION_BLOCK_OFFSET
        leveldat.write_file(leveldat_path)
        
        server.run(verbose)
    
    # reset spawn point 
    leveldat["Data"]["SpawnX"].value = spawn_x
    leveldat["Data"]["SpawnZ"].value = spawn_z
    leveldat.write_file(leveldat_path)

def bounds(s):
    try:
        minx, minz, maxx, maxz = map(int, s.split(","))
        return (minx, minz, maxx, maxz)
    except:
        raise argparse.ArgumentTypeError("Bounds must be minx,minz,maxx,maxz")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action='store_true')
    parser.add_argument("--include", metavar="<bounds>", type=bounds, required=True, 
                        help="size of the world in iterations, " 
                        + "of the format 'minX:minZ:maxX:maxZ', "
                        + "for example: '-4,-4,4,4'")
    parser.add_argument("--exclude", metavar="<bounds>", type=bounds, default=None)
    parser.add_argument("--seed", metavar="<seed>", default=None)
    parser.add_argument("--server-port", metavar="<server-port>", default=9521)
    parser.add_argument("worlddir")
    args = parser.parse_args()
    
    serverdir = join("/tmp", "mcwexpand-%d-%s" % (time.time(), random_string(6)))
    server = Server(serverdir, args.worlddir, args.seed)
    server.create_serverdir(join(dirname(__file__), "server"))
    
    print "Using %s as server directory" % serverdir
    
    # empty log file
    open(LOGFILE, "w").close()
    expand_world(server, args.include, args.exclude, args.verbose)

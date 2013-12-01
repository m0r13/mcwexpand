#!/usr/bin/env python2

import os
import argparse
import subprocess
import shutil
from nbt import nbt

# server generates at the start 25x25 chunks
# we use a small tolerance
ITERATION_BLOCK_OFFSET = 24 * 16

# add an option for this later
LOGFILE = os.path.join(os.path.dirname(__file__), "mcwexpand.log")

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

def run_server(verbose=False):
    kwargs = {
         "cwd" : os.path.join(os.path.dirname(__file__), "server"), 
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

def write_server_config(worlddir, seed):
    server = os.path.join(os.path.dirname(__file__), "server")
    template = os.path.join(server, "server.properties.tpl")
    template_to = os.path.join(server, "server.properties")
    template_vars = {
        "level-name" : os.path.relpath(worlddir, server),
    }
    if seed is not None:
        template_vars["level-seed"] = seed
    copy_template(template, template_to, template_vars)

def expand_world(worlddir, include, exclude=None, verbose=False):    
    print "Running server for the first time..."
    run_server(verbose)
    
    leveldat_path = os.path.join(worlddir, "level.dat")
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
        
        run_server(verbose)
    
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
    
    write_server_config(args.worlddir, args.seed)
    
    # empty log file
    open(LOGFILE, "w").close()
    expand_world(args.worlddir, args.include, args.exclude, args.verbose)

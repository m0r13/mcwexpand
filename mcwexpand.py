#!/usr/bin/env python2

import os
import argparse
import subprocess
from nbt import nbt

# server generates at the start 25x25 chunks
# we use a small tolerance
ITERATION_BLOCK_OFFSET = 24 * 16

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
    p = subprocess.Popen(["java", "-jar", "minecraft_server.jar", "nogui"], **kwargs)
    
    p.stdin.write("stop\n")
    if verbose:
        while 42:
            line = p.stdout.readline()
            if not line:
                break
            line = line.rstrip()
            print line
    else:
        p.wait()

def expand_world(worlddir, bounds, verbose=False):
    server = os.path.join(os.path.dirname(__file__), "server")
    template = os.path.join(server, "server.properties.tpl")
    template_to = os.path.join(server, "server.properties")
    template_vars = {
        "level-name" : os.path.relpath(worlddir, server)
    }
    copy_template(template, template_to, template_vars)
    
    print "Running server for the first time..."
    run_server(verbose)
    
    leveldat_path = os.path.join(worlddir, "level.dat")
    leveldat = nbt.NBTFile(filename=leveldat_path)
    spawn_x = leveldat["Data"]["SpawnX"].value
    spawn_z = leveldat["Data"]["SpawnZ"].value
    print "Found original spawn point: %d:%d" % (spawn_x, spawn_z)
    
    include = list(iterate_bounds(bounds))
    print "Doing %d iterations..." % len(include)
    i = 0
    for dx, dz in include:
        i += 1
        
        print "[%d/%d] Generating %d, %d ..." % (i, len(include), dx, dz)
        leveldat["Data"]["SpawnX"].value = spawn_x + dx*ITERATION_BLOCK_OFFSET
        leveldat["Data"]["SpawnZ"].value = spawn_z + dz*ITERATION_BLOCK_OFFSET
        leveldat.write_file(leveldat_path)
        
        run_server(verbose)

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
    parser.add_argument("worlddir")
    args = parser.parse_args()
    
    expand_world(args.worlddir, args.include, args.verbose)
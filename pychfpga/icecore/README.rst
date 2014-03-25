ICEBoard Python/C Repository
============================

This folder contains the code that provides the core of the McGill ICE
framework. This includes:

   * Hardware map management
   * Automatic discovery of ICE Resources: IceBoard (motherboards) and IceBoxes (backplanes)
   * Multithreaded dispatching of function calls and variable accesses across multiple boards
   * API to control and monitor basic hardware functions
   * Implement automatic system protection
   * Implements basic system monitoring
   * Handles system logs and exceptions

The content of this folder is a mirror of a main repository maintained by
McGill.  Do not change files here, as the chages might be overriden. Consider
this as a read-only folder.

The Python code runs on Python 2.7 and requires the following packages:
   * futures  ( to have access to concurrent.futures, which executes multiple processes in parallel)
   * sqlalchemy ( the object-oriented high-level SQL database interface)

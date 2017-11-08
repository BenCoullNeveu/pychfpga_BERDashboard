/* chi-exec run things on chime nodes
 *
 * Copyright (C) 2017 D. V. Wiebe
 *
 ***************************************************************************
 *
 * This program is free software; you can redistribute it and/or modify it under
 * the terms of the GNU Lesser General Public License as published by the
 * Free Software Foundation; either version 2.1 of the License, or (at your
 * option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
 */

#include <stdlib.h>

#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

/* SSH options */
#define SSH "/usr/bin/ssh"
#define KEYFILE "/root/.ssh/id_rsa"
#define REMOTE_USER "root"

/* Node count */
#define NN 16

/* Node name length, including trailing NUL */
#define NODELEN (sizeof "chi##")

/* Node name sprintf format */
#define NODEFMT "chi%02d"

/* Mash all the arguments containing the remote command into one buffer.
 * Returns NULL on error, otherwise a malloc'd string containing the command.
 */
static char *make_command(int argc, const char **argv) {
  int i;
  char *buffer = NULL; /* The command will end up in this buffer */
  size_t len = 0; /* The length of the command string including the trailing NUL */
  size_t size = 0; /* The size of the memory buffer */

  /* Loop over arguments */
  for (i = 0; i < argc; ++i) {
    size_t nextlen;

    /* If this is the start of the command, strip leading whitespace */
    if (len == 0)
      while (argv[i][0] == ' ' || argv[i][0] == '\t')
        argv[i]++;

    /* Ignore empty arguments */
    if (argv[i][0] == 0)
      continue;

    nextlen = strlen(argv[i]) + 1;

    /* Resize buffer if needed */
    if (len + nextlen > size) {
      char *ptr;
      size_t newsize = ((nextlen > size) ? nextlen : size) + size;

      ptr = realloc(buffer, newsize);

      if (ptr == NULL) {
        perror("realloc");
        free(buffer);
        return NULL;
      }
      buffer = ptr;
      size = newsize;
    }

    /* Replace the current trailing NUL with a space */
    if (len > 0)
      buffer[len - 1] = ' ';

    /* Copy next part of command */
    memcpy(buffer + len, argv[i], nextlen);
    len += nextlen;
  }

  /* Check for an empty command */
  if (buffer == NULL || buffer[0] == 0) {
    fputs("Empty command\n", stderr);
    free(buffer);
    return NULL;
  }

  /* Done */
  return buffer;
}

/* Set everything from start (if non-zero) to end.  Returns non-zero on error */
static int set_nodes(int start, int end, int nodes[NN])
{
  int n;

  if (end == 0) {
    /* This is either "0" per se, or things like ",," or "3-," */
    fputs("Node number out of range or missing\n", stderr);
    return 1;
  } else if (start == 0) {
    /* If start is zero, this isn't a range.  Make it one. */
    start = end;
  } else if (start > end) {
    /* This is, e.g., "5-2" (but we do allow "5-5") */
    fputs("Bad range in node specification\n", stderr);
    return 1;
  }
  
  /* Node numbers start from 1, but in the node list we start from zero */
  for (n = start; n <= end; ++n)
    nodes[n - 1] = 1;

  return 0;
}

/* Randomise a list of NN sequential numbers in nodes */
static void randomise_nodes(int nodes[NN])
{
  unsigned int seed = time(NULL);

  int i;

  /* Initialise the RNG */
  srand(seed);

  /* Initialise the nodes */
  for (i = 0; i < NN; ++i)
    nodes[i] = i;

  /* shuffle: swap the i'th item with a random one
   * (which might be itself) */
  for (i = 0; i < NN; ++i) {
    int q = nodes[i];
    int r = rand() % NN;
    nodes[i] = nodes[r];
    nodes[r] = q;
  }
}

/* Run cmd on node n.  Returns non-zero on error */
static int run_node(int n, char *cmd)
{
  /* Space for the nodename */
  char nodename[NODELEN];

  /* Child return status */
  int status;

  /* Child's PID */
  pid_t pid;

  /* Make node name */
  sprintf(nodename, NODEFMT, n + 1);
  printf("\n========== %s ==========\n", nodename);

  /* Fork */
  pid = fork();
  if (pid < 0) {
    perror("fork");
    return 1;
  }

  if (pid == 0) {
    /* === CHILD === */

    /* This is the SSH command, i.e.:
     *
     * /usr/bin/ssh -i <keyfile> -l <username> <nodename> -- <command>
     *
     * The "--" before the command is to prevent nefarious insertion of
     * extra ssh options
     */
    char *const args[] = { SSH, "-i", KEYFILE, "-l", REMOTE_USER,
      nodename, "--", cmd, NULL };

    /* Set our real UID to root */
    if (setuid(0)) {
      perror("setuid");
      return 1;
    }

    /* Exec.  This should not return */
    execvp(SSH, args);

    /* Exec failed */
    perror("execvp");
    return 1;
  }

  /* === PARENT === */

  /* Wait to reap the child */
  if (wait(&status) < 0) {
    perror("wait");
    return 1;
  }

  /* Check if ssh failed */
  if (WEXITSTATUS(status)) {
    fputs("ssh call failed\n", stderr);
    return 1;
  }

  return 0;
}

/* Parse the node string.  Returns non-zero on error */
static int parse_nodes(const char *ptr, int nodes[NN])
{
  /* The place where we build up numbers */
  unsigned accumulator = 0;

  /* The first node in a range */
  unsigned start = 0;

  /* Zero everything */
  memset(nodes, 0, sizeof(*nodes) * NN);

  /* Loop over characters */
  for (; *ptr; ++ptr) {
    if (*ptr >= '0' && *ptr <= '9') {
      /* A digit: left shift current accumulator and add the digit */
      accumulator = accumulator * 10 + *ptr - '0';
      
      /* Check value */
      if (accumulator > NN) {
        fputs("Node number out of range\n", stderr);
        return 1;
      }
    } else if (*ptr == ',') {
      /* End of number: set nodes and reset accumulator and start */
      if (set_nodes(start, accumulator, nodes))
        return 1;
      start = accumulator = 0;
    } else if (*ptr == '-') {
      /* Range: set start and reset accumulator */
      if (accumulator == 0) {
        /* This is, e.g., "-3" or ",-3" or "3--4" */
        fputs("Invalid node range\n", stderr);
        return 1;
      } else if (start > 0) {
        /* This is, e.g., "3-4-5" */
        fputs("Too many dashes in node specification\n", stderr);
        return 1;
      }
      start = accumulator;
      accumulator = 0;
    } else {
      /* Other crud */
      fputs("Bad character in node specification\n", stderr);
      return 1;
    }
  }

  /* Deal with the last element.  If the supplied node
   * argument didn't specify any nodes, this will return error
   */
  return set_nodes(start, accumulator, nodes);
}

/* Print usage and exit with retval.  Doesn't return. */
void Usage(const char *argv0, int retval)
{
  printf(
  "Usage:\n  %s <list-of-nodes> <command>\n"
  "to run on the nodes specified, or\n"
  "  %s single <command>\nto run on a single node chosen at random."
  "\n\nExample:\n  %s 2-4,7,12 ls -lah /home\n", argv0, argv0);

  exit(retval);
}

int main(int argc, const char **argv)
{
  /* A place to put a descriptor */
  int fd;

  /* The number of nodes with error */
  int n_error = 0;

  /* The number of nodes attempted */
  int n_total = 0;

  /* The list of nodes */
  int n, nodes[NN];

  /* Non-zero to run command on a single node at (pseudo-random) */
  int single = 0;

  /* The remote command goes here */
  char *cmd;

  /* Parse command line */
  if (argc < 3) {
    fputs("Missing argument\n", stderr);
    Usage(argv[0], 1);
  }

  if ((strcmp(argv[1], "-h") == 0) || (strcmp(argv[1], "--help") == 0))
    Usage(argv[0], 0);

  if (strcmp(argv[1], "single") == 0) {
    randomise_nodes(nodes);
    single = 1;
  } else if (parse_nodes(argv[1], nodes))
    Usage(argv[0], 1);

  /* Smush everything else together to form the command */
  if ((cmd = make_command(argc - 2, argv + 2)) == NULL)
    return 1;

  /* Make sure we can access the key file as EUID */
  if ((fd = open(KEYFILE, O_RDONLY)) < 0) {
    perror("Unable to access key file");
    exit(1);
  }
  close(fd);

  /* In single mode, nodes[] contains an ordered list of nodes to hit.
   * in non-single mdoe, nodes[] is non-zero for nodes which should be hit
   */
  if (single) {
    n_error = 1;
    for (n = 0; n < NN; ++n)
      if (run_node(nodes[n], cmd) == 0) {
        n_error = 0; /* It worked */
        break; /* So, stop trying */
      }
  } else
    for (n = 0; n < NN; ++n)
      if (nodes[n]) {
        if (run_node(n, cmd))
          n_error++;
        n_total++;
      }

  /* Done! */
  free(cmd);

  if (n_error > 0) {
    if (single) {
      fprintf(stderr, "\n"
          "========== COMMAND FAILED =============\n"
          "Couldn't find one working node!\n"
          "Check output above.\n"
          "========== COMMAND FAILED =============\n");
    } else if (n_total > 1) {
      fprintf(stderr, "\n"
          "========== COMMAND FAILED =============\n"
          "%i of %i nodes returned failure.\n"
          "Check output above.\n"
          "========== COMMAND FAILED =============\n", n_error, n_total);
    } else {
      fprintf(stderr, "\n"
          "========== COMMAND FAILED =============\n"
          "Node returned failure.\n"
          "Check output above.\n"
          "========== COMMAND FAILED =============\n", n_error, n_total);
    }
    return 1;
  }

  return 0;
}

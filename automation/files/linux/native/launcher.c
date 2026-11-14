#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* Resolve relative to the ELF executable, including launches from a file manager. */
int main(int argc, char **argv) {
    char executable[PATH_MAX];
    ssize_t length = readlink("/proc/self/exe", executable, sizeof(executable) - 1);
    if (length < 0 || (size_t)length >= sizeof(executable) - 1) {
        fprintf(stderr, "Cannot locate the game executable.\n");
        return 1;
    }
    executable[length] = '\0';
    char *separator = strrchr(executable, '/');
    if (separator == NULL) return 1;
    *separator = '\0';

    char runtime[PATH_MAX], script[PATH_MAX], java[PATH_MAX];
    int runtime_length = snprintf(runtime, sizeof(runtime), "%s/linux/runtime", executable);
    int script_length = snprintf(script, sizeof(script), "%s/play-linux.sh", executable);
    int java_length = snprintf(java, sizeof(java), "%s/bin/java", runtime);
    if (runtime_length < 0 || (size_t)runtime_length >= sizeof(runtime) ||
        script_length < 0 || (size_t)script_length >= sizeof(script) ||
        java_length < 0 || (size_t)java_length >= sizeof(java)) {
        fprintf(stderr, "Game directory path is too long.\n");
        return 1;
    }
    if (access(java, X_OK) != 0 || access(script, X_OK) != 0) {
        fprintf(stderr, "Keep DW3-Online-Linux beside play-linux.sh and the linux/ directory.\n");
        return 1;
    }
    if (setenv("JAVA_HOME", runtime, 1) != 0) {
        perror("Cannot select bundled Java");
        return 1;
    }
    char **arguments = calloc((size_t)argc + 1, sizeof(*arguments));
    if (arguments == NULL) {
        perror("Cannot allocate launcher arguments");
        return 1;
    }
    arguments[0] = script;
    for (int index = 1; index < argc; index++) arguments[index] = argv[index];
    execv(script, arguments);
    fprintf(stderr, "Could not launch the game: %s\n", strerror(errno));
    free(arguments);
    return 1;
}

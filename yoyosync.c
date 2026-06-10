#include <unistd.h>
#include <sys/wait.h>
int main(void){
    pid_t pid = fork();
    if (pid == 0) {
        execl("/usr/bin/python3", "python3",
              "/Users/yolanda-/yoyo-dashboard/export_reminders.py", (char*)0);
        _exit(127);
    }
    int st; waitpid(pid, &st, 0);
    return WIFEXITED(st) ? WEXITSTATUS(st) : 1;
}

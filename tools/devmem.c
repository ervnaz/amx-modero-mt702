#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdint.h>
#include <setjmp.h>
#include <signal.h>
static sigjmp_buf jb;
static void onfault(int s){ siglongjmp(jb,1); }
int main(int argc,char**argv){
  if(argc<3){fprintf(stderr,"usage: %s <hexaddr> <nwords>\n",argv[0]);return 1;}
  unsigned long addr=strtoul(argv[1],0,16);
  long n=strtol(argv[2],0,0);
  int fd=open("/dev/mem",O_RDONLY|O_SYNC);
  if(fd<0){perror("open");return 1;}
  unsigned long page=addr&~0xFFFUL, off=addr&0xFFF;
  size_t len=(off+n*4+0xFFF)&~0xFFFUL;
  volatile uint32_t*m=mmap(0,len,PROT_READ,MAP_SHARED,fd,page);
  if(m==MAP_FAILED){perror("mmap");return 1;}
  signal(SIGBUS,onfault); signal(SIGSEGV,onfault);
  volatile uint32_t*p=(volatile uint32_t*)((char*)m+off);
  for(long i=0;i<n;i++){
    if(sigsetjmp(jb,1)==0){ uint32_t v=p[i]; printf("%08lx %08x\n",addr+i*4,v); }
    else { printf("%08lx FAULT\n",addr+i*4); }
  }
  return 0;
}

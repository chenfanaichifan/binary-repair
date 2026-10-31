set pagination off
set confirm off
set breakpoint pending on
break *0x4012b0
commands
 silent
 printf "BADSINK_ENTRY pc=%p\n", $pc
 x/2i 0x4012b0
 info proc mappings
 dump binary memory /var/tmp/gate5b-work/tail-memory.bin 0x4018e9 0x402000
 quit
end
run

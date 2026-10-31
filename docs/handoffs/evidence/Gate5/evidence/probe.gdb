set pagination off
set confirm off
set breakpoint pending on
break *0x401304
commands
 silent
 printf "SITE pc=%p rsp=%p rdi=%p rsi=%p\n", $pc,$rsp,$rdi,$rsi
 continue
end
break *0x4018e9
commands
 silent
 printf "CAVE pc=%p rsp=%p\n", $pc,$rsp
 x/12i $pc
 info proc mappings
 dump binary memory /var/tmp/gate5-work/cave-memory.bin 0x4018e9 0x402000
 continue
end
break *0x401309
commands
 silent
 printf "AFTER pc=%p rsp=%p rax=%p\n", $pc,$rsp,$rax
 continue
end
break *0x401317
commands
 silent
 printf "RET pc=%p rsp=%p\n", $pc,$rsp
 continue
end
run

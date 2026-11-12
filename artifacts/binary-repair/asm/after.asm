0x4012b0: f30f1efa                 endbr64  
0x4012b4: 55                       push     rbp
0x4012b5: 4889e5                   mov      rbp, rsp
0x4012b8: 4883ec50                 sub      rsp, 0x50
0x4012bc: 48897db8                 mov      qword ptr [rbp - 0x48], rdi
0x4012c0: 48c745c000000000         mov      qword ptr [rbp - 0x40], 0
0x4012c8: 48c745c800000000         mov      qword ptr [rbp - 0x38], 0
0x4012d0: 48c745d000000000         mov      qword ptr [rbp - 0x30], 0
0x4012d8: 48c745d800000000         mov      qword ptr [rbp - 0x28], 0
0x4012e0: 48c745e000000000         mov      qword ptr [rbp - 0x20], 0
0x4012e8: 48c745e800000000         mov      qword ptr [rbp - 0x18], 0
0x4012f0: 66c745f00000             mov      word ptr [rbp - 0x10], 0
0x4012f6: 488b55b8                 mov      rdx, qword ptr [rbp - 0x48]
0x4012fa: 488d45c0                 lea      rax, [rbp - 0x40]
0x4012fe: 4889d6                   mov      rsi, rdx
0x401301: 4889c7                   mov      rdi, rax
0x401304: e8e0050000               call     0x4018e9
0x401309: 488b45b8                 mov      rax, qword ptr [rbp - 0x48]
0x40130d: 4889c7                   mov      rdi, rax
0x401310: e86b000000               call     0x401380
0x401315: 90                       nop      
0x401316: c9                       leave    
0x401317: c3                       ret      

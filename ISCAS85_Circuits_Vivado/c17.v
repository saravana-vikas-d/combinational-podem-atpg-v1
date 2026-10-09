// Verilog
// c17
// Ninputs 5
// Noutputs 2
// NtotalGates 6
// NAND2 6

// Vivado copy: each ISCAS gate is a DONT_TOUCH LUT, not a Verilog primitive.
// Verilog nand/nor/xnor become and/or/xor + not unless mapped to LUTs.
// Add this file AND iscas_vivado_gates.v to the Vivado project.
// synth_design -flatten_hierarchy none -no_lc -resource_sharing off

(* DONT_TOUCH = "TRUE" *)
module c17 (N1,N2,N3,N6,N7,N22,N23);

input N1,N2,N3,N6,N7;

output N22,N23;

wire N10,N11,N16,N19;

iscas_nand2 NAND2_1 (N10, N1, N3);
iscas_nand2 NAND2_2 (N11, N3, N6);
iscas_nand2 NAND2_3 (N16, N2, N11);
iscas_nand2 NAND2_4 (N19, N11, N7);
iscas_nand2 NAND2_5 (N22, N10, N16);
iscas_nand2 NAND2_6 (N23, N16, N19);

endmodule
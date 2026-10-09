// Vivado copy: each ISCAS gate is a DONT_TOUCH LUT, not a Verilog primitive.
// Verilog nand/nor/xnor become and/or/xor + not unless mapped to LUTs.
// Add this file AND iscas_vivado_gates.v to the Vivado project.
// synth_design -flatten_hierarchy none -no_lc -resource_sharing off

(* DONT_TOUCH = "TRUE" *)
module ex1(N1, N2, N3, N6);
input N1, N2, N3
output N6;
wire N4;

iscas_and2 AND2_1 (N4, N1, N2);
iscas_and2 AND2_1 (N6, N3, N4);

endmodule
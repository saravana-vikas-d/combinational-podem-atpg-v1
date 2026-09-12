module ex1(N1, N2, N3, N6);
input N1, N2, N3
output N6;
wire N4;

and AND2_1 (N4, N1, N2);
and AND2_1 (N6, N3, N4);

endmodule
// 7-series LUT wrappers for ISCAS primitives.
// nand/nor/xnor are LUT INIT values, not and/or/xor plus an inverter.
// Add this file to every Vivado project that uses ISCAS85_Circuits_Vivado.

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_and2 (O, I0, I1);
  output O;
  input I0, I1;
  (* DONT_TOUCH = "TRUE" *)
  LUT2 #(.INIT(4'h8)) _lut (.O(O), .I0(I0), .I1(I1));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_and3 (O, I0, I1, I2);
  output O;
  input I0, I1, I2;
  (* DONT_TOUCH = "TRUE" *)
  LUT3 #(.INIT(8'h80)) _lut (.O(O), .I0(I0), .I1(I1), .I2(I2));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_and4 (O, I0, I1, I2, I3);
  output O;
  input I0, I1, I2, I3;
  (* DONT_TOUCH = "TRUE" *)
  LUT4 #(.INIT(16'h8000)) _lut (.O(O), .I0(I0), .I1(I1), .I2(I2), .I3(I3));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_and5 (O, I0, I1, I2, I3, I4);
  output O;
  input I0, I1, I2, I3, I4;
  (* DONT_TOUCH = "TRUE" *)
  LUT5 #(.INIT(32'h80000000)) _lut (.O(O), .I0(I0), .I1(I1), .I2(I2), .I3(I3), .I4(I4));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_and8 (O, I0, I1, I2, I3, I4, I5, I6, I7);
  output O;
  input I0, I1, I2, I3, I4, I5, I6, I7;
  wire _partial;
  (* DONT_TOUCH = "TRUE" *)
  LUT6 #(.INIT(64'h8000000000000000)) _lut0 (.O(_partial), .I0(I0), .I1(I1), .I2(I2), .I3(I3), .I4(I4), .I5(I5));
  (* DONT_TOUCH = "TRUE" *)
  LUT3 #(.INIT(8'h80)) _lut1 (.O(O), .I0(_partial), .I1(I6), .I2(I7));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_and9 (O, I0, I1, I2, I3, I4, I5, I6, I7, I8);
  output O;
  input I0, I1, I2, I3, I4, I5, I6, I7, I8;
  wire _partial;
  (* DONT_TOUCH = "TRUE" *)
  LUT6 #(.INIT(64'h8000000000000000)) _lut0 (.O(_partial), .I0(I0), .I1(I1), .I2(I2), .I3(I3), .I4(I4), .I5(I5));
  (* DONT_TOUCH = "TRUE" *)
  LUT4 #(.INIT(16'h8000)) _lut1 (.O(O), .I0(_partial), .I1(I6), .I2(I7), .I3(I8));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_buf1 (O, I0);
  output O;
  input I0;
  (* DONT_TOUCH = "TRUE" *)
  LUT1 #(.INIT(2'h2)) _lut (.O(O), .I0(I0));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_nand2 (O, I0, I1);
  output O;
  input I0, I1;
  (* DONT_TOUCH = "TRUE" *)
  LUT2 #(.INIT(4'h7)) _lut (.O(O), .I0(I0), .I1(I1));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_nand3 (O, I0, I1, I2);
  output O;
  input I0, I1, I2;
  (* DONT_TOUCH = "TRUE" *)
  LUT3 #(.INIT(8'h7F)) _lut (.O(O), .I0(I0), .I1(I1), .I2(I2));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_nand4 (O, I0, I1, I2, I3);
  output O;
  input I0, I1, I2, I3;
  (* DONT_TOUCH = "TRUE" *)
  LUT4 #(.INIT(16'h7FFF)) _lut (.O(O), .I0(I0), .I1(I1), .I2(I2), .I3(I3));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_nand5 (O, I0, I1, I2, I3, I4);
  output O;
  input I0, I1, I2, I3, I4;
  (* DONT_TOUCH = "TRUE" *)
  LUT5 #(.INIT(32'h7FFFFFFF)) _lut (.O(O), .I0(I0), .I1(I1), .I2(I2), .I3(I3), .I4(I4));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_nand8 (O, I0, I1, I2, I3, I4, I5, I6, I7);
  output O;
  input I0, I1, I2, I3, I4, I5, I6, I7;
  wire _partial;
  (* DONT_TOUCH = "TRUE" *)
  LUT6 #(.INIT(64'h8000000000000000)) _lut0 (.O(_partial), .I0(I0), .I1(I1), .I2(I2), .I3(I3), .I4(I4), .I5(I5));
  (* DONT_TOUCH = "TRUE" *)
  LUT3 #(.INIT(8'h7F)) _lut1 (.O(O), .I0(_partial), .I1(I6), .I2(I7));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_nor2 (O, I0, I1);
  output O;
  input I0, I1;
  (* DONT_TOUCH = "TRUE" *)
  LUT2 #(.INIT(4'h1)) _lut (.O(O), .I0(I0), .I1(I1));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_nor3 (O, I0, I1, I2);
  output O;
  input I0, I1, I2;
  (* DONT_TOUCH = "TRUE" *)
  LUT3 #(.INIT(8'h1)) _lut (.O(O), .I0(I0), .I1(I1), .I2(I2));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_nor4 (O, I0, I1, I2, I3);
  output O;
  input I0, I1, I2, I3;
  (* DONT_TOUCH = "TRUE" *)
  LUT4 #(.INIT(16'h1)) _lut (.O(O), .I0(I0), .I1(I1), .I2(I2), .I3(I3));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_nor8 (O, I0, I1, I2, I3, I4, I5, I6, I7);
  output O;
  input I0, I1, I2, I3, I4, I5, I6, I7;
  wire _partial;
  (* DONT_TOUCH = "TRUE" *)
  LUT6 #(.INIT(64'hFFFFFFFFFFFFFFFE)) _lut0 (.O(_partial), .I0(I0), .I1(I1), .I2(I2), .I3(I3), .I4(I4), .I5(I5));
  (* DONT_TOUCH = "TRUE" *)
  LUT3 #(.INIT(8'h1)) _lut1 (.O(O), .I0(_partial), .I1(I6), .I2(I7));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_not1 (O, I0);
  output O;
  input I0;
  (* DONT_TOUCH = "TRUE" *)
  LUT1 #(.INIT(2'h1)) _lut (.O(O), .I0(I0));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_or2 (O, I0, I1);
  output O;
  input I0, I1;
  (* DONT_TOUCH = "TRUE" *)
  LUT2 #(.INIT(4'hE)) _lut (.O(O), .I0(I0), .I1(I1));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_or3 (O, I0, I1, I2);
  output O;
  input I0, I1, I2;
  (* DONT_TOUCH = "TRUE" *)
  LUT3 #(.INIT(8'hFE)) _lut (.O(O), .I0(I0), .I1(I1), .I2(I2));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_or4 (O, I0, I1, I2, I3);
  output O;
  input I0, I1, I2, I3;
  (* DONT_TOUCH = "TRUE" *)
  LUT4 #(.INIT(16'hFFFE)) _lut (.O(O), .I0(I0), .I1(I1), .I2(I2), .I3(I3));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_or5 (O, I0, I1, I2, I3, I4);
  output O;
  input I0, I1, I2, I3, I4;
  (* DONT_TOUCH = "TRUE" *)
  LUT5 #(.INIT(32'hFFFFFFFE)) _lut (.O(O), .I0(I0), .I1(I1), .I2(I2), .I3(I3), .I4(I4));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_xnor2 (O, I0, I1);
  output O;
  input I0, I1;
  (* DONT_TOUCH = "TRUE" *)
  LUT2 #(.INIT(4'h9)) _lut (.O(O), .I0(I0), .I1(I1));
endmodule

(* DONT_TOUCH = "TRUE", KEEP_HIERARCHY = "TRUE" *)
module iscas_xor2 (O, I0, I1);
  output O;
  input I0, I1;
  (* DONT_TOUCH = "TRUE" *)
  LUT2 #(.INIT(4'h6)) _lut (.O(O), .I0(I0), .I1(I1));
endmodule


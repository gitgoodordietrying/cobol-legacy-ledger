*> ================================================================
*> TAXREC.cpy — Tax Bracket Table Layout
*> Used by: TAXCALC.cob
*> ================================================================
*>
*> PMR 1983: "Brackets change every year. Put them in a table
*> so we only update the copybook, not the program."
*> Reality: The program ALSO has hardcoded brackets that
*> override these. See TAXCALC.cob KNOWN_ISSUES.
*>
*> JRK 1992: Added bracket 06 for new top rate. Never tested.
*> SLW 1995: "Don't touch this. It works. I think."
*>
 01  TAX-BRACKET-TABLE.
     05  TAX-BRACKET-ENTRY OCCURS 6 TIMES.
         10  TAX-BRACKET-MIN     PIC S9(7)V99 COMP-3.
         10  TAX-BRACKET-MAX     PIC S9(7)V99 COMP-3.
         10  TAX-BRACKET-RATE    PIC 9V9999.
         10  TAX-BRACKET-LABEL   PIC X(15).

*> PMR: Working fields for tax computation
 01  TAX-WORK-FIELDS.
     05  TAX-GROSS-PAY           PIC S9(7)V99 COMP-3.
     05  TAX-FED-AMOUNT          PIC S9(7)V99 COMP-3.
     05  TAX-STATE-AMOUNT        PIC S9(7)V99 COMP-3.
     05  TAX-FICA-AMOUNT         PIC S9(7)V99 COMP-3.
     05  TAX-TOTAL-AMOUNT        PIC S9(7)V99 COMP-3.
     05  TAX-NET-PAY             PIC S9(7)V99 COMP-3.
     05  TAX-WORK-RATE           PIC 9V9999.
     05  TAX-WORK-BASE           PIC S9(7)V99 COMP-3.
*>   JRK 1992: Temp field for "new algorithm". Never used.
     05  TAX-WORK-TEMP           PIC S9(9)V99 COMP-3.
     05  TAX-ERROR-FLAG          PIC X(1).
         88  TAX-OK              VALUE 'N'.
         88  TAX-ERROR           VALUE 'Y'.

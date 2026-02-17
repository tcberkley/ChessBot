/**********************************\
 ==================================
           
             Didactic
       BITBOARD CHESS ENGINE     
       
                by
                
         Code Monkey King

 ==================================
\**********************************/

/**********************************\
 ==================================

      THIS ENGINE IS DEDICATED
    TO HOBBY PROGRAMMERS FACING
      ISSUES WITH READING CODE
    OF OPEN SOURCE CHESS ENGINES
  --------------------------------
   This engine is incredibly easy
  to read and understand. It uses
   global variables everywhere it
   is possible and sometimes even
 sacrifices performance for clarity

 ==================================
\**********************************/

/**********************************\
 ==================================
  
   THIS PROGRAM IS FREE SOFTWARE.
   IT COMES WITHOUT ANY WARRANTY,
    TO THE EXTENT PERMITTED BY
          APPLICABLE LAW.
         
   YOU CAN REDISTRIBUTE IT AND/OR
    MODIFY IT UNDER THE TERMS OF
  THE DO WHAT THE FUCK YOU WANT TO
      PUBLIC LICENCE VERSION 2
     AS PUBLISHED BY SAM HOCEVAR
      SEE http://www.wtfpl.net/
          FOR MORE DETAILS
          
  --------------------------------
    Copyright © 2020 Maksim Korzh
   <freesoft.for.people@gmail.com>
   
 ==================================
\**********************************/

/**********************************\
 ==================================
  
     DO WHAT THE FUCK YOU WANT
        TO PUBLIC LICENSE
  --------------------------------
     Version 2, December 2004
  --------------------------------
    Everyone is permitted to copy
      and distribute verbatim or
   modified copies of this license
    document, and changing it is
         allowed as long as
        the name is changed
  --------------------------------
      DO WHAT THE FUCK YOU WANT
         TO PUBLIC LICENSE
  TERMS AND CONDITIONS FOR COPYING,
    DISTRIBUTION AND MODIFICATION
  
   0. You just DO WHAT THE FUCK
                 YOU WANT TO.
  --------------------------------
   Copyright (C) 2004 Sam Hocevar
        <sam@hocevar.net>
   
 ==================================
\**********************************/


// system headers
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <unistd.h>
#ifdef WIN64
    #include <windows.h>
#else
    # include <sys/time.h>
#endif

// define bitboard data type
#define U64 unsigned long long

// FEN dedug positions
#define empty_board "8/8/8/8/8/8/8/8 b - - "
#define start_position "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1 "
#define tricky_position "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1 "
#define killer_position "rnbqkb1r/pp1p1pPp/8/2p1pP2/1P1P4/3P3P/P1P1P3/RNBQKBNR w KQkq e6 0 1"
#define cmk_position "r2q1rk1/ppp2ppp/2n1bn2/2b1p3/3pP3/3P1NPP/PPP1NPB1/R1BQ1RK1 b - - 0 9 "
#define repetitions "2r3k1/R7/8/1R6/8/8/P4KPP/8 w - - 0 40 "

// board squares
enum {
    a8, b8, c8, d8, e8, f8, g8, h8,
    a7, b7, c7, d7, e7, f7, g7, h7,
    a6, b6, c6, d6, e6, f6, g6, h6,
    a5, b5, c5, d5, e5, f5, g5, h5,
    a4, b4, c4, d4, e4, f4, g4, h4,
    a3, b3, c3, d3, e3, f3, g3, h3,
    a2, b2, c2, d2, e2, f2, g2, h2,
    a1, b1, c1, d1, e1, f1, g1, h1, no_sq
};

// encode pieces
enum { P, N, B, R, Q, K, p, n, b, r, q, k };

// sides to move (colors)
enum { white, black, both };

// bishop and rook
enum { rook, bishop };

// castling rights binary encoding

/*

    bin  dec
    
   0001    1  white king can castle to the king side
   0010    2  white king can castle to the queen side
   0100    4  black king can castle to the king side
   1000    8  black king can castle to the queen side

   examples

   1111       both sides an castle both directions
   1001       black king => queen side
              white king => king side

*/

enum { wk = 1, wq = 2, bk = 4, bq = 8 };

// convert squares to coordinates
const char *square_to_coordinates[] = {
    "a8", "b8", "c8", "d8", "e8", "f8", "g8", "h8",
    "a7", "b7", "c7", "d7", "e7", "f7", "g7", "h7",
    "a6", "b6", "c6", "d6", "e6", "f6", "g6", "h6",
    "a5", "b5", "c5", "d5", "e5", "f5", "g5", "h5",
    "a4", "b4", "c4", "d4", "e4", "f4", "g4", "h4",
    "a3", "b3", "c3", "d3", "e3", "f3", "g3", "h3",
    "a2", "b2", "c2", "d2", "e2", "f2", "g2", "h2",
    "a1", "b1", "c1", "d1", "e1", "f1", "g1", "h1",
};

// ASCII pieces
char ascii_pieces[12] = "PNBRQKpnbrqk";

// unicode pieces
char *unicode_pieces[12] = {"♙", "♘", "♗", "♖", "♕", "♔", "♟︎", "♞", "♝", "♜", "♛", "♚"};

// convert ASCII character pieces to encoded constants
int char_pieces[] = {
    ['P'] = P,
    ['N'] = N,
    ['B'] = B,
    ['R'] = R,
    ['Q'] = Q,
    ['K'] = K,
    ['p'] = p,
    ['n'] = n,
    ['b'] = b,
    ['r'] = r,
    ['q'] = q,
    ['k'] = k
};

// promoted pieces
char promoted_pieces[] = {
    [Q] = 'q',
    [R] = 'r',
    [B] = 'b',
    [N] = 'n',
    [q] = 'q',
    [r] = 'r',
    [b] = 'b',
    [n] = 'n'
};


/**********************************\
 ==================================
 
            Chess board
 
 ==================================
\**********************************/

/*
                            WHITE PIECES


        Pawns                  Knights              Bishops
        
  8  0 0 0 0 0 0 0 0    8  0 0 0 0 0 0 0 0    8  0 0 0 0 0 0 0 0
  7  0 0 0 0 0 0 0 0    7  0 0 0 0 0 0 0 0    7  0 0 0 0 0 0 0 0
  6  0 0 0 0 0 0 0 0    6  0 0 0 0 0 0 0 0    6  0 0 0 0 0 0 0 0
  5  0 0 0 0 0 0 0 0    5  0 0 0 0 0 0 0 0    5  0 0 0 0 0 0 0 0
  4  0 0 0 0 0 0 0 0    4  0 0 0 0 0 0 0 0    4  0 0 0 0 0 0 0 0
  3  0 0 0 0 0 0 0 0    3  0 0 0 0 0 0 0 0    3  0 0 0 0 0 0 0 0
  2  1 1 1 1 1 1 1 1    2  0 0 0 0 0 0 0 0    2  0 0 0 0 0 0 0 0
  1  0 0 0 0 0 0 0 0    1  0 1 0 0 0 0 1 0    1  0 0 1 0 0 1 0 0

     a b c d e f g h       a b c d e f g h       a b c d e f g h


         Rooks                 Queens                 King

  8  0 0 0 0 0 0 0 0    8  0 0 0 0 0 0 0 0    8  0 0 0 0 0 0 0 0
  7  0 0 0 0 0 0 0 0    7  0 0 0 0 0 0 0 0    7  0 0 0 0 0 0 0 0
  6  0 0 0 0 0 0 0 0    6  0 0 0 0 0 0 0 0    6  0 0 0 0 0 0 0 0
  5  0 0 0 0 0 0 0 0    5  0 0 0 0 0 0 0 0    5  0 0 0 0 0 0 0 0
  4  0 0 0 0 0 0 0 0    4  0 0 0 0 0 0 0 0    4  0 0 0 0 0 0 0 0
  3  0 0 0 0 0 0 0 0    3  0 0 0 0 0 0 0 0    3  0 0 0 0 0 0 0 0
  2  0 0 0 0 0 0 0 0    2  0 0 0 0 0 0 0 0    2  0 0 0 0 0 0 0 0
  1  1 0 0 0 0 0 0 1    1  0 0 0 1 0 0 0 0    1  0 0 0 0 1 0 0 0

     a b c d e f g h       a b c d e f g h       a b c d e f g h


                            BLACK PIECES


        Pawns                  Knights              Bishops
        
  8  0 0 0 0 0 0 0 0    8  0 1 0 0 0 0 1 0    8  0 0 1 0 0 1 0 0
  7  1 1 1 1 1 1 1 1    7  0 0 0 0 0 0 0 0    7  0 0 0 0 0 0 0 0
  6  0 0 0 0 0 0 0 0    6  0 0 0 0 0 0 0 0    6  0 0 0 0 0 0 0 0
  5  0 0 0 0 0 0 0 0    5  0 0 0 0 0 0 0 0    5  0 0 0 0 0 0 0 0
  4  0 0 0 0 0 0 0 0    4  0 0 0 0 0 0 0 0    4  0 0 0 0 0 0 0 0
  3  0 0 0 0 0 0 0 0    3  0 0 0 0 0 0 0 0    3  0 0 0 0 0 0 0 0
  2  0 0 0 0 0 0 0 0    2  0 0 0 0 0 0 0 0    2  0 0 0 0 0 0 0 0
  1  0 0 0 0 0 0 0 0    1  0 0 0 0 0 0 0 0    1  0 0 0 0 0 0 0 0

     a b c d e f g h       a b c d e f g h       a b c d e f g h


         Rooks                 Queens                 King

  8  1 0 0 0 0 0 0 1    8  0 0 0 1 0 0 0 0    8  0 0 0 0 1 0 0 0
  7  0 0 0 0 0 0 0 0    7  0 0 0 0 0 0 0 0    7  0 0 0 0 0 0 0 0
  6  0 0 0 0 0 0 0 0    6  0 0 0 0 0 0 0 0    6  0 0 0 0 0 0 0 0
  5  0 0 0 0 0 0 0 0    5  0 0 0 0 0 0 0 0    5  0 0 0 0 0 0 0 0
  4  0 0 0 0 0 0 0 0    4  0 0 0 0 0 0 0 0    4  0 0 0 0 0 0 0 0
  3  0 0 0 0 0 0 0 0    3  0 0 0 0 0 0 0 0    3  0 0 0 0 0 0 0 0
  2  0 0 0 0 0 0 0 0    2  0 0 0 0 0 0 0 0    2  0 0 0 0 0 0 0 0
  1  0 0 0 0 0 0 0 0    1  0 0 0 0 0 0 0 0    1  0 0 0 0 0 0 0 0

     a b c d e f g h       a b c d e f g h       a b c d e f g h



                             OCCUPANCIES


     White occupancy       Black occupancy       All occupancies

  8  0 0 0 0 0 0 0 0    8  1 1 1 1 1 1 1 1    8  1 1 1 1 1 1 1 1
  7  0 0 0 0 0 0 0 0    7  1 1 1 1 1 1 1 1    7  1 1 1 1 1 1 1 1
  6  0 0 0 0 0 0 0 0    6  0 0 0 0 0 0 0 0    6  0 0 0 0 0 0 0 0
  5  0 0 0 0 0 0 0 0    5  0 0 0 0 0 0 0 0    5  0 0 0 0 0 0 0 0
  4  0 0 0 0 0 0 0 0    4  0 0 0 0 0 0 0 0    4  0 0 0 0 0 0 0 0
  3  0 0 0 0 0 0 0 0    3  0 0 0 0 0 0 0 0    3  0 0 0 0 0 0 0 0
  2  1 1 1 1 1 1 1 1    2  0 0 0 0 0 0 0 0    2  1 1 1 1 1 1 1 1
  1  1 1 1 1 1 1 1 1    1  0 0 0 0 0 0 0 0    1  1 1 1 1 1 1 1 1



                            ALL TOGETHER

                        8  ♜ ♞ ♝ ♛ ♚ ♝ ♞ ♜
                        7  ♟︎ ♟︎ ♟︎ ♟︎ ♟︎ ♟︎ ♟︎ ♟︎
                        6  . . . . . . . .
                        5  . . . . . . . .
                        4  . . . . . . . .
                        3  . . . . . . . .
                        2  ♙ ♙ ♙ ♙ ♙ ♙ ♙ ♙
                        1  ♖ ♘ ♗ ♕ ♔ ♗ ♘ ♖

                           a b c d e f g h

*/

// piece bitboards
U64 bitboards[12];

// occupancy bitboards
U64 occupancies[3];

// side to move
int side;

// enpassant square
int enpassant = no_sq; 

// castling rights
int castle;

// "almost" unique position identifier aka hash key or position key
U64 hash_key;

// positions repetition table
U64 repetition_table[1000];  // 1000 is a number of plies (500 moves) in the entire game

// repetition index
int repetition_index;

// half move counter
int ply;

// v12 additions: castling tracking and fullmove number
int has_castled[2]; // has_castled[white], has_castled[black]
int fullmove_number = 1;


/**********************************\
 ==================================
 
       Time controls variables
 
 ==================================
\**********************************/

// exit from engine flag
int quit = 0;

// UCI "movestogo" command moves counter
int movestogo = 30;

// UCI "movetime" command time counter
int movetime = -1;

// UCI "time" command holder (ms)
int bbc_time = -1;

// UCI "inc" command's time increment holder
int inc = 0;

// UCI "starttime" command time holder
int starttime = 0;

// UCI "stoptime" command time holder
int stoptime = 0;

// variable to flag time control availability
int timeset = 0;

// variable to flag when the time is up
int stopped = 0;


/**********************************\
 ==================================
 
       Miscellaneous functions
          forked from VICE
         by Richard Allbert
 
 ==================================
\**********************************/

// get time in milliseconds
int get_time_ms()
{
    #ifdef WIN64
        return GetTickCount();
    #else
        struct timeval time_value;
        gettimeofday(&time_value, NULL);
        return time_value.tv_sec * 1000 + time_value.tv_usec / 1000;
    #endif
}

/*

  Function to "listen" to GUI's input during search.
  It's waiting for the user input from STDIN.
  OS dependent.
  
  First Richard Allbert aka BluefeverSoftware grabbed it from somewhere...
  And then Code Monkey King has grabbed it from VICE)
  
*/
  
int input_waiting()
{
    #ifndef WIN32
        fd_set readfds;
        struct timeval tv;
        FD_ZERO (&readfds);
        FD_SET (fileno(stdin), &readfds);
        tv.tv_sec=0; tv.tv_usec=0;
        select(16, &readfds, 0, 0, &tv);

        return (FD_ISSET(fileno(stdin), &readfds));
    #else
        static int init = 0, pipe;
        static HANDLE inh;
        DWORD dw;

        if (!init)
        {
            init = 1;
            inh = GetStdHandle(STD_INPUT_HANDLE);
            pipe = !GetConsoleMode(inh, &dw);
            if (!pipe)
            {
                SetConsoleMode(inh, dw & ~(ENABLE_MOUSE_INPUT|ENABLE_WINDOW_INPUT));
                FlushConsoleInputBuffer(inh);
            }
        }
        
        if (pipe)
        {
           if (!PeekNamedPipe(inh, NULL, 0, NULL, &dw, NULL)) return 1;
           return dw;
        }
        
        else
        {
           GetNumberOfConsoleInputEvents(inh, &dw);
           return dw <= 1 ? 0 : dw;
        }

    #endif
}

// read GUI/user input
void read_input()
{
    // bytes to read holder
    int bytes;
    
    // GUI/user input
    char input[256] = "", *endc;

    // "listen" to STDIN
    if (input_waiting())
    {
        // tell engine to stop calculating
        stopped = 1;
        
        // loop to read bytes from STDIN
        do
        {
            // read bytes from STDIN
            bytes=read(fileno(stdin), input, 256);
        }
        
        // until bytes available
        while (bytes < 0);
        
        // searches for the first occurrence of '\n'
        endc = strchr(input,'\n');
        
        // if found new line set value at pointer to 0
        if (endc) *endc=0;
        
        // if input is available
        if (strlen(input) > 0)
        {
            // match UCI "quit" command
            if (!strncmp(input, "quit", 4))
            {
                // tell engine to terminate exacution    
                quit = 1;
            }

            // // match UCI "stop" command
            else if (!strncmp(input, "stop", 4))    {
                // tell engine to terminate exacution
                quit = 1;
            }
        }   
    }
}

// a bridge function to interact between search and GUI input
static void communicate() {
	// if time is up break here
    if(timeset == 1 && get_time_ms() > stoptime) {
		// tell engine to stop calculating
		stopped = 1;
	}
	
    // read GUI input
	read_input();
}


/**********************************\
 ==================================
 
           Random numbers
 
 ==================================
\**********************************/

// pseudo random number state
unsigned int random_state = 1804289383;

// generate 32-bit pseudo legal numbers
unsigned int get_random_U32_number()
{
    // get current state
    unsigned int number = random_state;
    
    // XOR shift algorithm
    number ^= number << 13;
    number ^= number >> 17;
    number ^= number << 5;
    
    // update random number state
    random_state = number;
    
    // return random number
    return number;
}

// generate 64-bit pseudo legal numbers
U64 get_random_U64_number()
{
    // define 4 random numbers
    U64 n1, n2, n3, n4;
    
    // init random numbers slicing 16 bits from MS1B side
    n1 = (U64)(get_random_U32_number()) & 0xFFFF;
    n2 = (U64)(get_random_U32_number()) & 0xFFFF;
    n3 = (U64)(get_random_U32_number()) & 0xFFFF;
    n4 = (U64)(get_random_U32_number()) & 0xFFFF;
    
    // return random number
    return n1 | (n2 << 16) | (n3 << 32) | (n4 << 48);
}

// generate magic number candidate
U64 generate_magic_number()
{
    return get_random_U64_number() & get_random_U64_number() & get_random_U64_number();
}


/**********************************\
 ==================================
 
          Bit manipulations
 
 ==================================
\**********************************/

// set/get/pop bit macros
#define set_bit(bitboard, square) ((bitboard) |= (1ULL << (square)))
#define get_bit(bitboard, square) ((bitboard) & (1ULL << (square)))
#define pop_bit(bitboard, square) ((bitboard) &= ~(1ULL << (square)))

// count bits within a bitboard (Brian Kernighan's way)
static inline int count_bits(U64 bitboard)
{
    // bit counter
    int count = 0;
    
    // consecutively reset least significant 1st bit
    while (bitboard)
    {
        // increment count
        count++;
        
        // reset least significant 1st bit
        bitboard &= bitboard - 1;
    }
    
    // return bit count
    return count;
}

// get least significant 1st bit index
static inline int get_ls1b_index(U64 bitboard)
{
    // make sure bitboard is not 0
    if (bitboard)
    {
        // count trailing bits before LS1B
        return count_bits((bitboard & -bitboard) - 1);
    }
    
    //otherwise
    else
        // return illegal index
        return -1;
}


/**********************************\
 ==================================
 
            Zobrist keys
 
 ==================================
\**********************************/

// random piece keys [piece][square]
U64 piece_keys[12][64];

// random enpassant keys [square]
U64 enpassant_keys[64];

// random castling keys
U64 castle_keys[16];

// random side key
U64 side_key;

// init random hash keys
void init_random_keys()
{
    // update pseudo random number state
    random_state = 1804289383;

    // loop over piece codes
    for (int piece = P; piece <= k; piece++)
    {
        // loop over board squares
        for (int square = 0; square < 64; square++)
            // init random piece keys
            piece_keys[piece][square] = get_random_U64_number();
    }
    
    // loop over board squares
    for (int square = 0; square < 64; square++)
        // init random enpassant keys
        enpassant_keys[square] = get_random_U64_number();
    
    // loop over castling keys
    for (int index = 0; index < 16; index++)
        // init castling keys
        castle_keys[index] = get_random_U64_number();
        
    // init random side key
    side_key = get_random_U64_number();
}

// generate "almost" unique position ID aka hash key from scratch
U64 generate_hash_key()
{
    // final hash key
    U64 final_key = 0ULL;
    
    // temp piece bitboard copy
    U64 bitboard;
    
    // loop over piece bitboards
    for (int piece = P; piece <= k; piece++)
    {
        // init piece bitboard copy
        bitboard = bitboards[piece];
        
        // loop over the pieces within a bitboard
        while (bitboard)
        {
            // init square occupied by the piece
            int square = get_ls1b_index(bitboard);
            
            // hash piece
            final_key ^= piece_keys[piece][square];
            
            // pop LS1B
            pop_bit(bitboard, square);
        }
    }
    
    // if enpassant square is on board
    if (enpassant != no_sq)
        // hash enpassant
        final_key ^= enpassant_keys[enpassant];
    
    // hash castling rights
    final_key ^= castle_keys[castle];
    
    // hash the side only if black is to move
    if (side == black) final_key ^= side_key;
    
    // return generated hash key
    return final_key;
}


/**********************************\
 ==================================
 
           Input & Output
 
 ==================================
\**********************************/

// print bitboard
void print_bitboard(U64 bitboard)
{
    // print offset
    printf("\n");

    // loop over board ranks
    for (int rank = 0; rank < 8; rank++)
    {
        // loop over board files
        for (int file = 0; file < 8; file++)
        {
            // convert file & rank into square index
            int square = rank * 8 + file;
            
            // print ranks
            if (!file)
                printf("  %d ", 8 - rank);
            
            // print bit state (either 1 or 0)
            printf(" %d", get_bit(bitboard, square) ? 1 : 0);
            
        }
        
        // print new line every rank
        printf("\n");
    }
    
    // print board files
    printf("\n     a b c d e f g h\n\n");
    
    // print bitboard as unsigned decimal number
    printf("     Bitboard: %llud\n\n", bitboard);
}

// print board
void print_board()
{
    // print offset
    printf("\n");

    // loop over board ranks
    for (int rank = 0; rank < 8; rank++)
    {
        // loop ober board files
        for (int file = 0; file < 8; file++)
        {
            // init square
            int square = rank * 8 + file;
            
            // print ranks
            if (!file)
                printf("  %d ", 8 - rank);
            
            // define piece variable
            int piece = -1;
            
            // loop over all piece bitboards
            for (int bb_piece = P; bb_piece <= k; bb_piece++)
            {
                // if there is a piece on current square
                if (get_bit(bitboards[bb_piece], square))
                    // get piece code
                    piece = bb_piece;
            }
            
            // print different piece set depending on OS
            #ifdef WIN64
                printf(" %c", (piece == -1) ? '.' : ascii_pieces[piece]);
            #else
                printf(" %s", (piece == -1) ? "." : unicode_pieces[piece]);
            #endif
        }
        
        // print new line every rank
        printf("\n");
    }
    
    // print board files
    printf("\n     a b c d e f g h\n\n");
    
    // print side to move
    printf("     Side:     %s\n", !side ? "white" : "black");
    
    // print enpassant square
    printf("     Enpassant:   %s\n", (enpassant != no_sq) ? square_to_coordinates[enpassant] : "no");
    
    // print castling rights
    printf("     Castling:  %c%c%c%c\n\n", (castle & wk) ? 'K' : '-',
                                           (castle & wq) ? 'Q' : '-',
                                           (castle & bk) ? 'k' : '-',
                                           (castle & bq) ? 'q' : '-');
    
    // print hash key
    printf("     Hash key:  %llx\n\n", hash_key);
}

// parse FEN string
void parse_fen(char *fen)
{
    // reset board position (bitboards)
    memset(bitboards, 0ULL, sizeof(bitboards));
    
    // reset occupancies (bitboards)
    memset(occupancies, 0ULL, sizeof(occupancies));
    
    // reset game state variables
    side = 0;
    enpassant = no_sq;
    castle = 0;

    // reset v13 state
    has_castled[0] = 0; has_castled[1] = 0;
    fullmove_number = 1;

    // reset repetition index
    repetition_index = 0;
    
    // reset repetition table
    memset(repetition_table, 0ULL, sizeof(repetition_table));
    
    // loop over board ranks
    for (int rank = 0; rank < 8; rank++)
    {
        // loop over board files
        for (int file = 0; file < 8; file++)
        {
            // init current square
            int square = rank * 8 + file;
            
            // match ascii pieces within FEN string
            if ((*fen >= 'a' && *fen <= 'z') || (*fen >= 'A' && *fen <= 'Z'))
            {
                // init piece type
                int piece = char_pieces[*fen];
                
                // set piece on corresponding bitboard
                set_bit(bitboards[piece], square);
                
                // increment pointer to FEN string
                fen++;
            }
            
            // match empty square numbers within FEN string
            if (*fen >= '0' && *fen <= '9')
            {
                // init offset (convert char 0 to int 0)
                int offset = *fen - '0';
                
                // define piece variable
                int piece = -1;
                
                // loop over all piece bitboards
                for (int bb_piece = P; bb_piece <= k; bb_piece++)
                {
                    // if there is a piece on current square
                    if (get_bit(bitboards[bb_piece], square))
                        // get piece code
                        piece = bb_piece;
                }
                
                // on empty current square
                if (piece == -1)
                    // decrement file
                    file--;
                
                // adjust file counter
                file += offset;
                
                // increment pointer to FEN string
                fen++;
            }
            
            // match rank separator
            if (*fen == '/')
                // increment pointer to FEN string
                fen++;
        }
    }
    
    // got to parsing side to move (increment pointer to FEN string)
    fen++;
    
    // parse side to move
    (*fen == 'w') ? (side = white) : (side = black);
    
    // go to parsing castling rights
    fen += 2;
    
    // parse castling rights
    while (*fen != ' ')
    {
        switch (*fen)
        {
            case 'K': castle |= wk; break;
            case 'Q': castle |= wq; break;
            case 'k': castle |= bk; break;
            case 'q': castle |= bq; break;
            case '-': break;
        }

        // increment pointer to FEN string
        fen++;
    }
    
    // got to parsing enpassant square (increment pointer to FEN string)
    fen++;
    
    // parse enpassant square
    if (*fen != '-')
    {
        // parse enpassant file & rank
        int file = fen[0] - 'a';
        int rank = 8 - (fen[1] - '0');
        
        // init enpassant square
        enpassant = rank * 8 + file;
    }
    
    // no enpassant square
    else
        enpassant = no_sq;

    // advance fen pointer past en passant field
    while (*fen && *fen != ' ') fen++;

    // parse halfmove clock (skip it, we don't use it)
    if (*fen == ' ') {
        fen++;
        while (*fen && *fen != ' ') fen++;
    }

    // parse fullmove number
    if (*fen == ' ') {
        fen++;
        fullmove_number = atoi(fen);
        if (fullmove_number < 1) fullmove_number = 1;
    }

    // loop over white pieces bitboards
    for (int piece = P; piece <= K; piece++)
        // populate white occupancy bitboard
        occupancies[white] |= bitboards[piece];
    
    // loop over black pieces bitboards
    for (int piece = p; piece <= k; piece++)
        // populate white occupancy bitboard
        occupancies[black] |= bitboards[piece];
    
    // init all occupancies
    occupancies[both] |= occupancies[white];
    occupancies[both] |= occupancies[black];
    
    // init hash key
    hash_key = generate_hash_key();
}


/**********************************\
 ==================================
 
              Attacks
 
 ==================================
\**********************************/

/* 
     not A file          not H file         not HG files      not AB files
      bitboard            bitboard            bitboard          bitboard

 8  0 1 1 1 1 1 1 1    1 1 1 1 1 1 1 0    1 1 1 1 1 1 0 0    0 0 1 1 1 1 1 1
 7  0 1 1 1 1 1 1 1    1 1 1 1 1 1 1 0    1 1 1 1 1 1 0 0    0 0 1 1 1 1 1 1
 6  0 1 1 1 1 1 1 1    1 1 1 1 1 1 1 0    1 1 1 1 1 1 0 0    0 0 1 1 1 1 1 1
 5  0 1 1 1 1 1 1 1    1 1 1 1 1 1 1 0    1 1 1 1 1 1 0 0    0 0 1 1 1 1 1 1
 4  0 1 1 1 1 1 1 1    1 1 1 1 1 1 1 0    1 1 1 1 1 1 0 0    0 0 1 1 1 1 1 1
 3  0 1 1 1 1 1 1 1    1 1 1 1 1 1 1 0    1 1 1 1 1 1 0 0    0 0 1 1 1 1 1 1
 2  0 1 1 1 1 1 1 1    1 1 1 1 1 1 1 0    1 1 1 1 1 1 0 0    0 0 1 1 1 1 1 1
 1  0 1 1 1 1 1 1 1    1 1 1 1 1 1 1 0    1 1 1 1 1 1 0 0    0 0 1 1 1 1 1 1
    
    a b c d e f g h    a b c d e f g h    a b c d e f g h    a b c d e f g h

*/

// not A file constant
const U64 not_a_file = 18374403900871474942ULL;

// not H file constant
const U64 not_h_file = 9187201950435737471ULL;

// not HG file constant
const U64 not_hg_file = 4557430888798830399ULL;

// not AB file constant
const U64 not_ab_file = 18229723555195321596ULL;

// bishop relevant occupancy bit count for every square on board
const int bishop_relevant_bits[64] = {
    6, 5, 5, 5, 5, 5, 5, 6, 
    5, 5, 5, 5, 5, 5, 5, 5, 
    5, 5, 7, 7, 7, 7, 5, 5, 
    5, 5, 7, 9, 9, 7, 5, 5, 
    5, 5, 7, 9, 9, 7, 5, 5, 
    5, 5, 7, 7, 7, 7, 5, 5, 
    5, 5, 5, 5, 5, 5, 5, 5, 
    6, 5, 5, 5, 5, 5, 5, 6
};

// rook relevant occupancy bit count for every square on board
const int rook_relevant_bits[64] = {
    12, 11, 11, 11, 11, 11, 11, 12, 
    11, 10, 10, 10, 10, 10, 10, 11, 
    11, 10, 10, 10, 10, 10, 10, 11, 
    11, 10, 10, 10, 10, 10, 10, 11, 
    11, 10, 10, 10, 10, 10, 10, 11, 
    11, 10, 10, 10, 10, 10, 10, 11, 
    11, 10, 10, 10, 10, 10, 10, 11, 
    12, 11, 11, 11, 11, 11, 11, 12
};

// rook magic numbers
U64 rook_magic_numbers[64] = {
    0x8a80104000800020ULL,
    0x140002000100040ULL,
    0x2801880a0017001ULL,
    0x100081001000420ULL,
    0x200020010080420ULL,
    0x3001c0002010008ULL,
    0x8480008002000100ULL,
    0x2080088004402900ULL,
    0x800098204000ULL,
    0x2024401000200040ULL,
    0x100802000801000ULL,
    0x120800800801000ULL,
    0x208808088000400ULL,
    0x2802200800400ULL,
    0x2200800100020080ULL,
    0x801000060821100ULL,
    0x80044006422000ULL,
    0x100808020004000ULL,
    0x12108a0010204200ULL,
    0x140848010000802ULL,
    0x481828014002800ULL,
    0x8094004002004100ULL,
    0x4010040010010802ULL,
    0x20008806104ULL,
    0x100400080208000ULL,
    0x2040002120081000ULL,
    0x21200680100081ULL,
    0x20100080080080ULL,
    0x2000a00200410ULL,
    0x20080800400ULL,
    0x80088400100102ULL,
    0x80004600042881ULL,
    0x4040008040800020ULL,
    0x440003000200801ULL,
    0x4200011004500ULL,
    0x188020010100100ULL,
    0x14800401802800ULL,
    0x2080040080800200ULL,
    0x124080204001001ULL,
    0x200046502000484ULL,
    0x480400080088020ULL,
    0x1000422010034000ULL,
    0x30200100110040ULL,
    0x100021010009ULL,
    0x2002080100110004ULL,
    0x202008004008002ULL,
    0x20020004010100ULL,
    0x2048440040820001ULL,
    0x101002200408200ULL,
    0x40802000401080ULL,
    0x4008142004410100ULL,
    0x2060820c0120200ULL,
    0x1001004080100ULL,
    0x20c020080040080ULL,
    0x2935610830022400ULL,
    0x44440041009200ULL,
    0x280001040802101ULL,
    0x2100190040002085ULL,
    0x80c0084100102001ULL,
    0x4024081001000421ULL,
    0x20030a0244872ULL,
    0x12001008414402ULL,
    0x2006104900a0804ULL,
    0x1004081002402ULL
};

// bishop magic numbers
U64 bishop_magic_numbers[64] = {
    0x40040844404084ULL,
    0x2004208a004208ULL,
    0x10190041080202ULL,
    0x108060845042010ULL,
    0x581104180800210ULL,
    0x2112080446200010ULL,
    0x1080820820060210ULL,
    0x3c0808410220200ULL,
    0x4050404440404ULL,
    0x21001420088ULL,
    0x24d0080801082102ULL,
    0x1020a0a020400ULL,
    0x40308200402ULL,
    0x4011002100800ULL,
    0x401484104104005ULL,
    0x801010402020200ULL,
    0x400210c3880100ULL,
    0x404022024108200ULL,
    0x810018200204102ULL,
    0x4002801a02003ULL,
    0x85040820080400ULL,
    0x810102c808880400ULL,
    0xe900410884800ULL,
    0x8002020480840102ULL,
    0x220200865090201ULL,
    0x2010100a02021202ULL,
    0x152048408022401ULL,
    0x20080002081110ULL,
    0x4001001021004000ULL,
    0x800040400a011002ULL,
    0xe4004081011002ULL,
    0x1c004001012080ULL,
    0x8004200962a00220ULL,
    0x8422100208500202ULL,
    0x2000402200300c08ULL,
    0x8646020080080080ULL,
    0x80020a0200100808ULL,
    0x2010004880111000ULL,
    0x623000a080011400ULL,
    0x42008c0340209202ULL,
    0x209188240001000ULL,
    0x400408a884001800ULL,
    0x110400a6080400ULL,
    0x1840060a44020800ULL,
    0x90080104000041ULL,
    0x201011000808101ULL,
    0x1a2208080504f080ULL,
    0x8012020600211212ULL,
    0x500861011240000ULL,
    0x180806108200800ULL,
    0x4000020e01040044ULL,
    0x300000261044000aULL,
    0x802241102020002ULL,
    0x20906061210001ULL,
    0x5a84841004010310ULL,
    0x4010801011c04ULL,
    0xa010109502200ULL,
    0x4a02012000ULL,
    0x500201010098b028ULL,
    0x8040002811040900ULL,
    0x28000010020204ULL,
    0x6000020202d0240ULL,
    0x8918844842082200ULL,
    0x4010011029020020ULL
};

// pawn attacks table [side][square]
U64 pawn_attacks[2][64];

// knight attacks table [square]
U64 knight_attacks[64];

// king attacks table [square]
U64 king_attacks[64];

// bishop attack masks
U64 bishop_masks[64];

// rook attack masks
U64 rook_masks[64];

// bishop attacks table [square][occupancies]
U64 bishop_attacks[64][512];

// rook attacks rable [square][occupancies]
U64 rook_attacks[64][4096];

// generate pawn attacks
U64 mask_pawn_attacks(int side, int square)
{
    // result attacks bitboard
    U64 attacks = 0ULL;

    // piece bitboard
    U64 bitboard = 0ULL;
    
    // set piece on board
    set_bit(bitboard, square);
    
    // white pawns
    if (!side)
    {
        // generate pawn attacks
        if ((bitboard >> 7) & not_a_file) attacks |= (bitboard >> 7);
        if ((bitboard >> 9) & not_h_file) attacks |= (bitboard >> 9);
    }
    
    // black pawns
    else
    {
        // generate pawn attacks
        if ((bitboard << 7) & not_h_file) attacks |= (bitboard << 7);
        if ((bitboard << 9) & not_a_file) attacks |= (bitboard << 9);    
    }
    
    // return attack map
    return attacks;
}

// generate knight attacks
U64 mask_knight_attacks(int square)
{
    // result attacks bitboard
    U64 attacks = 0ULL;

    // piece bitboard
    U64 bitboard = 0ULL;
    
    // set piece on board
    set_bit(bitboard, square);
    
    // generate knight attacks
    if ((bitboard >> 17) & not_h_file) attacks |= (bitboard >> 17);
    if ((bitboard >> 15) & not_a_file) attacks |= (bitboard >> 15);
    if ((bitboard >> 10) & not_hg_file) attacks |= (bitboard >> 10);
    if ((bitboard >> 6) & not_ab_file) attacks |= (bitboard >> 6);
    if ((bitboard << 17) & not_a_file) attacks |= (bitboard << 17);
    if ((bitboard << 15) & not_h_file) attacks |= (bitboard << 15);
    if ((bitboard << 10) & not_ab_file) attacks |= (bitboard << 10);
    if ((bitboard << 6) & not_hg_file) attacks |= (bitboard << 6);

    // return attack map
    return attacks;
}

// generate king attacks
U64 mask_king_attacks(int square)
{
    // result attacks bitboard
    U64 attacks = 0ULL;

    // piece bitboard
    U64 bitboard = 0ULL;
    
    // set piece on board
    set_bit(bitboard, square);
    
    // generate king attacks
    if (bitboard >> 8) attacks |= (bitboard >> 8);
    if ((bitboard >> 9) & not_h_file) attacks |= (bitboard >> 9);
    if ((bitboard >> 7) & not_a_file) attacks |= (bitboard >> 7);
    if ((bitboard >> 1) & not_h_file) attacks |= (bitboard >> 1);
    if (bitboard << 8) attacks |= (bitboard << 8);
    if ((bitboard << 9) & not_a_file) attacks |= (bitboard << 9);
    if ((bitboard << 7) & not_h_file) attacks |= (bitboard << 7);
    if ((bitboard << 1) & not_a_file) attacks |= (bitboard << 1);
    
    // return attack map
    return attacks;
}

// mask bishop attacks
U64 mask_bishop_attacks(int square)
{
    // result attacks bitboard
    U64 attacks = 0ULL;
    
    // init ranks & files
    int r, f;
    
    // init target rank & files
    int tr = square / 8;
    int tf = square % 8;
    
    // mask relevant bishop occupancy bits
    for (r = tr + 1, f = tf + 1; r <= 6 && f <= 6; r++, f++) attacks |= (1ULL << (r * 8 + f));
    for (r = tr - 1, f = tf + 1; r >= 1 && f <= 6; r--, f++) attacks |= (1ULL << (r * 8 + f));
    for (r = tr + 1, f = tf - 1; r <= 6 && f >= 1; r++, f--) attacks |= (1ULL << (r * 8 + f));
    for (r = tr - 1, f = tf - 1; r >= 1 && f >= 1; r--, f--) attacks |= (1ULL << (r * 8 + f));
    
    // return attack map
    return attacks;
}

// mask rook attacks
U64 mask_rook_attacks(int square)
{
    // result attacks bitboard
    U64 attacks = 0ULL;
    
    // init ranks & files
    int r, f;
    
    // init target rank & files
    int tr = square / 8;
    int tf = square % 8;
    
    // mask relevant rook occupancy bits
    for (r = tr + 1; r <= 6; r++) attacks |= (1ULL << (r * 8 + tf));
    for (r = tr - 1; r >= 1; r--) attacks |= (1ULL << (r * 8 + tf));
    for (f = tf + 1; f <= 6; f++) attacks |= (1ULL << (tr * 8 + f));
    for (f = tf - 1; f >= 1; f--) attacks |= (1ULL << (tr * 8 + f));
    
    // return attack map
    return attacks;
}

// generate bishop attacks on the fly
U64 bishop_attacks_on_the_fly(int square, U64 block)
{
    // result attacks bitboard
    U64 attacks = 0ULL;
    
    // init ranks & files
    int r, f;
    
    // init target rank & files
    int tr = square / 8;
    int tf = square % 8;
    
    // generate bishop atacks
    for (r = tr + 1, f = tf + 1; r <= 7 && f <= 7; r++, f++)
    {
        attacks |= (1ULL << (r * 8 + f));
        if ((1ULL << (r * 8 + f)) & block) break;
    }
    
    for (r = tr - 1, f = tf + 1; r >= 0 && f <= 7; r--, f++)
    {
        attacks |= (1ULL << (r * 8 + f));
        if ((1ULL << (r * 8 + f)) & block) break;
    }
    
    for (r = tr + 1, f = tf - 1; r <= 7 && f >= 0; r++, f--)
    {
        attacks |= (1ULL << (r * 8 + f));
        if ((1ULL << (r * 8 + f)) & block) break;
    }
    
    for (r = tr - 1, f = tf - 1; r >= 0 && f >= 0; r--, f--)
    {
        attacks |= (1ULL << (r * 8 + f));
        if ((1ULL << (r * 8 + f)) & block) break;
    }
    
    // return attack map
    return attacks;
}

// generate rook attacks on the fly
U64 rook_attacks_on_the_fly(int square, U64 block)
{
    // result attacks bitboard
    U64 attacks = 0ULL;
    
    // init ranks & files
    int r, f;
    
    // init target rank & files
    int tr = square / 8;
    int tf = square % 8;
    
    // generate rook attacks
    for (r = tr + 1; r <= 7; r++)
    {
        attacks |= (1ULL << (r * 8 + tf));
        if ((1ULL << (r * 8 + tf)) & block) break;
    }
    
    for (r = tr - 1; r >= 0; r--)
    {
        attacks |= (1ULL << (r * 8 + tf));
        if ((1ULL << (r * 8 + tf)) & block) break;
    }
    
    for (f = tf + 1; f <= 7; f++)
    {
        attacks |= (1ULL << (tr * 8 + f));
        if ((1ULL << (tr * 8 + f)) & block) break;
    }
    
    for (f = tf - 1; f >= 0; f--)
    {
        attacks |= (1ULL << (tr * 8 + f));
        if ((1ULL << (tr * 8 + f)) & block) break;
    }
    
    // return attack map
    return attacks;
}

// init leaper pieces attacks
void init_leapers_attacks()
{
    // loop over 64 board squares
    for (int square = 0; square < 64; square++)
    {
        // init pawn attacks
        pawn_attacks[white][square] = mask_pawn_attacks(white, square);
        pawn_attacks[black][square] = mask_pawn_attacks(black, square);
        
        // init knight attacks
        knight_attacks[square] = mask_knight_attacks(square);
        
        // init king attacks
        king_attacks[square] = mask_king_attacks(square);
    }
}

// set occupancies
U64 set_occupancy(int index, int bits_in_mask, U64 attack_mask)
{
    // occupancy map
    U64 occupancy = 0ULL;
    
    // loop over the range of bits within attack mask
    for (int count = 0; count < bits_in_mask; count++)
    {
        // get LS1B index of attacks mask
        int square = get_ls1b_index(attack_mask);
        
        // pop LS1B in attack map
        pop_bit(attack_mask, square);
        
        // make sure occupancy is on board
        if (index & (1 << count))
            // populate occupancy map
            occupancy |= (1ULL << square);
    }
    
    // return occupancy map
    return occupancy;
}


/**********************************\
 ==================================
 
               Magics
 
 ==================================
\**********************************/

// find appropriate magic number
U64 find_magic_number(int square, int relevant_bits, int bishop)
{
    // init occupancies
    U64 occupancies[4096];
    
    // init attack tables
    U64 attacks[4096];
    
    // init used attacks
    U64 used_attacks[4096];
    
    // init attack mask for a current piece
    U64 attack_mask = bishop ? mask_bishop_attacks(square) : mask_rook_attacks(square);
    
    // init occupancy indicies
    int occupancy_indicies = 1 << relevant_bits;
    
    // loop over occupancy indicies
    for (int index = 0; index < occupancy_indicies; index++)
    {
        // init occupancies
        occupancies[index] = set_occupancy(index, relevant_bits, attack_mask);
        
        // init attacks
        attacks[index] = bishop ? bishop_attacks_on_the_fly(square, occupancies[index]) :
                                    rook_attacks_on_the_fly(square, occupancies[index]);
    }
    
    // test magic numbers loop
    for (int random_count = 0; random_count < 100000000; random_count++)
    {
        // generate magic number candidate
        U64 magic_number = generate_magic_number();
        
        // skip inappropriate magic numbers
        if (count_bits((attack_mask * magic_number) & 0xFF00000000000000) < 6) continue;
        
        // init used attacks
        memset(used_attacks, 0ULL, sizeof(used_attacks));
        
        // init index & fail flag
        int index, fail;
        
        // test magic index loop
        for (index = 0, fail = 0; !fail && index < occupancy_indicies; index++)
        {
            // init magic index
            int magic_index = (int)((occupancies[index] * magic_number) >> (64 - relevant_bits));
            
            // if magic index works
            if (used_attacks[magic_index] == 0ULL)
                // init used attacks
                used_attacks[magic_index] = attacks[index];
            
            // otherwise
            else if (used_attacks[magic_index] != attacks[index])
                // magic index doesn't work
                fail = 1;
        }
        
        // if magic number works
        if (!fail)
            // return it
            return magic_number;
    }
    
    // if magic number doesn't work
    printf("  Magic number fails!\n");
    return 0ULL;
}

// init magic numbers
void init_magic_numbers()
{
    // loop over 64 board squares
    for (int square = 0; square < 64; square++)
        // init rook magic numbers
        rook_magic_numbers[square] = find_magic_number(square, rook_relevant_bits[square], rook);

    // loop over 64 board squares
    for (int square = 0; square < 64; square++)
        // init bishop magic numbers
        bishop_magic_numbers[square] = find_magic_number(square, bishop_relevant_bits[square], bishop);
}

// init slider piece's attack tables
void init_sliders_attacks(int bishop)
{
    // loop over 64 board squares
    for (int square = 0; square < 64; square++)
    {
        // init bishop & rook masks
        bishop_masks[square] = mask_bishop_attacks(square);
        rook_masks[square] = mask_rook_attacks(square);
        
        // init current mask
        U64 attack_mask = bishop ? bishop_masks[square] : rook_masks[square];
        
        // init relevant occupancy bit count
        int relevant_bits_count = count_bits(attack_mask);
        
        // init occupancy indicies
        int occupancy_indicies = (1 << relevant_bits_count);
        
        // loop over occupancy indicies
        for (int index = 0; index < occupancy_indicies; index++)
        {
            // bishop
            if (bishop)
            {
                // init current occupancy variation
                U64 occupancy = set_occupancy(index, relevant_bits_count, attack_mask);
                
                // init magic index
                int magic_index = (occupancy * bishop_magic_numbers[square]) >> (64 - bishop_relevant_bits[square]);
                
                // init bishop attacks
                bishop_attacks[square][magic_index] = bishop_attacks_on_the_fly(square, occupancy);
            }
            
            // rook
            else
            {
                // init current occupancy variation
                U64 occupancy = set_occupancy(index, relevant_bits_count, attack_mask);
                
                // init magic index
                int magic_index = (occupancy * rook_magic_numbers[square]) >> (64 - rook_relevant_bits[square]);
                
                // init rook attacks
                rook_attacks[square][magic_index] = rook_attacks_on_the_fly(square, occupancy);
            
            }
        }
    }
}

// get bishop attacks
static inline U64 get_bishop_attacks(int square, U64 occupancy)
{
    // get bishop attacks assuming current board occupancy
    occupancy &= bishop_masks[square];
    occupancy *= bishop_magic_numbers[square];
    occupancy >>= 64 - bishop_relevant_bits[square];
    
    // return bishop attacks
    return bishop_attacks[square][occupancy];
}

// get rook attacks
static inline U64 get_rook_attacks(int square, U64 occupancy)
{
    // get rook attacks assuming current board occupancy
    occupancy &= rook_masks[square];
    occupancy *= rook_magic_numbers[square];
    occupancy >>= 64 - rook_relevant_bits[square];
    
    // return rook attacks
    return rook_attacks[square][occupancy];
}

// get queen attacks
static inline U64 get_queen_attacks(int square, U64 occupancy)
{
    // init result attacks bitboard
    U64 queen_attacks = 0ULL;
    
    // init bishop occupancies
    U64 bishop_occupancy = occupancy;
    
    // init rook occupancies
    U64 rook_occupancy = occupancy;
    
    // get bishop attacks assuming current board occupancy
    bishop_occupancy &= bishop_masks[square];
    bishop_occupancy *= bishop_magic_numbers[square];
    bishop_occupancy >>= 64 - bishop_relevant_bits[square];
    
    // get bishop attacks
    queen_attacks = bishop_attacks[square][bishop_occupancy];
    
    // get rook attacks assuming current board occupancy
    rook_occupancy &= rook_masks[square];
    rook_occupancy *= rook_magic_numbers[square];
    rook_occupancy >>= 64 - rook_relevant_bits[square];
    
    // get rook attacks
    queen_attacks |= rook_attacks[square][rook_occupancy];
    
    // return queen attacks
    return queen_attacks;
}


/**********************************\
 ==================================
 
           Move generator
 
 ==================================
\**********************************/

// is square current given attacked by the current given side
static inline int is_square_attacked(int square, int side)
{
    // attacked by white pawns
    if ((side == white) && (pawn_attacks[black][square] & bitboards[P])) return 1;
    
    // attacked by black pawns
    if ((side == black) && (pawn_attacks[white][square] & bitboards[p])) return 1;
    
    // attacked by knights
    if (knight_attacks[square] & ((side == white) ? bitboards[N] : bitboards[n])) return 1;
    
    // attacked by bishops
    if (get_bishop_attacks(square, occupancies[both]) & ((side == white) ? bitboards[B] : bitboards[b])) return 1;

    // attacked by rooks
    if (get_rook_attacks(square, occupancies[both]) & ((side == white) ? bitboards[R] : bitboards[r])) return 1;    

    // attacked by bishops
    if (get_queen_attacks(square, occupancies[both]) & ((side == white) ? bitboards[Q] : bitboards[q])) return 1;
    
    // attacked by kings
    if (king_attacks[square] & ((side == white) ? bitboards[K] : bitboards[k])) return 1;

    // by default return false
    return 0;
}

// print attacked squares
void print_attacked_squares(int side)
{
    printf("\n");
    
    // loop over board ranks
    for (int rank = 0; rank < 8; rank++)
    {
        // loop over board files
        for (int file = 0; file < 8; file++)
        {
            // init square
            int square = rank * 8 + file;
            
            // print ranks
            if (!file)
                printf("  %d ", 8 - rank);
            
            // check whether current square is attacked or not
            printf(" %d", is_square_attacked(square, side) ? 1 : 0);
        }
        
        // print new line every rank
        printf("\n");
    }
    
    // print files
    printf("\n     a b c d e f g h\n\n");
}

/*
          binary move bits                               hexidecimal constants
    
    0000 0000 0000 0000 0011 1111    source square       0x3f
    0000 0000 0000 1111 1100 0000    target square       0xfc0
    0000 0000 1111 0000 0000 0000    piece               0xf000
    0000 1111 0000 0000 0000 0000    promoted piece      0xf0000
    0001 0000 0000 0000 0000 0000    capture flag        0x100000
    0010 0000 0000 0000 0000 0000    double push flag    0x200000
    0100 0000 0000 0000 0000 0000    enpassant flag      0x400000
    1000 0000 0000 0000 0000 0000    castling flag       0x800000
*/

// encode move
#define encode_move(source, target, piece, promoted, capture, double, enpassant, castling) \
    (source) |          \
    (target << 6) |     \
    (piece << 12) |     \
    (promoted << 16) |  \
    (capture << 20) |   \
    (double << 21) |    \
    (enpassant << 22) | \
    (castling << 23)    \
    
// extract source square
#define get_move_source(move) (move & 0x3f)

// extract target square
#define get_move_target(move) ((move & 0xfc0) >> 6)

// extract piece
#define get_move_piece(move) ((move & 0xf000) >> 12)

// extract promoted piece
#define get_move_promoted(move) ((move & 0xf0000) >> 16)

// extract capture flag
#define get_move_capture(move) (move & 0x100000)

// extract double pawn push flag
#define get_move_double(move) (move & 0x200000)

// extract enpassant flag
#define get_move_enpassant(move) (move & 0x400000)

// extract castling flag
#define get_move_castling(move) (move & 0x800000)

// move list structure
typedef struct {
    // moves
    int moves[256];
    
    // move count
    int count;
} moves;

// add move to the move list
static inline void add_move(moves *move_list, int move)
{
    // strore move
    move_list->moves[move_list->count] = move;
    
    // increment move count
    move_list->count++;
}

// print move (for UCI purposes)
void print_move(int move)
{
    if (get_move_promoted(move))
        printf("%s%s%c", square_to_coordinates[get_move_source(move)],
                           square_to_coordinates[get_move_target(move)],
                           promoted_pieces[get_move_promoted(move)]);
    else
        printf("%s%s", square_to_coordinates[get_move_source(move)],
                           square_to_coordinates[get_move_target(move)]);
}


// print move list
void print_move_list(moves *move_list)
{
    // do nothing on empty move list
    if (!move_list->count)
    {
        printf("\n     No move in the move list!\n");
        return;
    }
    
    printf("\n     move    piece     capture   double    enpass    castling\n\n");
    
    // loop over moves within a move list
    for (int move_count = 0; move_count < move_list->count; move_count++)
    {
        // init move
        int move = move_list->moves[move_count];
        
        #ifdef WIN64
            // print move
            printf("      %s%s%c   %c         %d         %d         %d         %d\n", square_to_coordinates[get_move_source(move)],
                                                                                  square_to_coordinates[get_move_target(move)],
                                                                                  get_move_promoted(move) ? promoted_pieces[get_move_promoted(move)] : ' ',
                                                                                  ascii_pieces[get_move_piece(move)],
                                                                                  get_move_capture(move) ? 1 : 0,
                                                                                  get_move_double(move) ? 1 : 0,
                                                                                  get_move_enpassant(move) ? 1 : 0,
                                                                                  get_move_castling(move) ? 1 : 0);
        #else
            // print move
            printf("     %s%s%c   %s         %d         %d         %d         %d\n", square_to_coordinates[get_move_source(move)],
                                                                                  square_to_coordinates[get_move_target(move)],
                                                                                  get_move_promoted(move) ? promoted_pieces[get_move_promoted(move)] : ' ',
                                                                                  unicode_pieces[get_move_piece(move)],
                                                                                  get_move_capture(move) ? 1 : 0,
                                                                                  get_move_double(move) ? 1 : 0,
                                                                                  get_move_enpassant(move) ? 1 : 0,
                                                                                  get_move_castling(move) ? 1 : 0);
        #endif
        
    }
    
    // print total number of moves
    printf("\n\n     Total number of moves: %d\n\n", move_list->count);

}

// preserve board state
#define copy_board()                                                      \
    U64 bitboards_copy[12], occupancies_copy[3];                          \
    int side_copy, enpassant_copy, castle_copy;                           \
    memcpy(bitboards_copy, bitboards, 96);                                \
    memcpy(occupancies_copy, occupancies, 24);                            \
    side_copy = side, enpassant_copy = enpassant, castle_copy = castle;   \
    U64 hash_key_copy = hash_key;                                         \
    int has_castled_copy[2]; memcpy(has_castled_copy, has_castled, 8);    \
    int fullmove_copy = fullmove_number;                                  \

// restore board state
#define take_back()                                                       \
    memcpy(bitboards, bitboards_copy, 96);                                \
    memcpy(occupancies, occupancies_copy, 24);                            \
    side = side_copy, enpassant = enpassant_copy, castle = castle_copy;   \
    hash_key = hash_key_copy;                                             \
    memcpy(has_castled, has_castled_copy, 8);                             \
    fullmove_number = fullmove_copy;                                      \

// move types
enum { all_moves, only_captures };

/*
                           castling   move     in      in
                              right update     binary  decimal

 king & rooks didn't move:     1111 & 1111  =  1111    15

        white king  moved:     1111 & 1100  =  1100    12
  white king's rook moved:     1111 & 1110  =  1110    14
 white queen's rook moved:     1111 & 1101  =  1101    13
     
         black king moved:     1111 & 0011  =  1011    3
  black king's rook moved:     1111 & 1011  =  1011    11
 black queen's rook moved:     1111 & 0111  =  0111    7

*/

// castling rights update constants
const int castling_rights[64] = {
     7, 15, 15, 15,  3, 15, 15, 11,
    15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15,
    13, 15, 15, 15, 12, 15, 15, 14
};

// make move on chess board
static inline int make_move(int move, int move_flag)
{
    // quiet moves
    if (move_flag == all_moves)
    {
        // preserve board state
        copy_board();
        
        // parse move
        int source_square = get_move_source(move);
        int target_square = get_move_target(move);
        int piece = get_move_piece(move);
        int promoted_piece = get_move_promoted(move);
        int capture = get_move_capture(move);
        int double_push = get_move_double(move);
        int enpass = get_move_enpassant(move);
        int castling = get_move_castling(move);
        
        // move piece
        pop_bit(bitboards[piece], source_square);
        set_bit(bitboards[piece], target_square);
        
        // hash piece
        hash_key ^= piece_keys[piece][source_square]; // remove piece from source square in hash key
        hash_key ^= piece_keys[piece][target_square]; // set piece to the target square in hash key
        
        // handling capture moves
        if (capture)
        {
            // pick up bitboard piece index ranges depending on side
            int start_piece, end_piece;
            
            // white to move
            if (side == white)
            {
                start_piece = p;
                end_piece = k;
            }
            
            // black to move
            else
            {
                start_piece = P;
                end_piece = K;
            }
            
            // loop over bitboards opposite to the current side to move
            for (int bb_piece = start_piece; bb_piece <= end_piece; bb_piece++)
            {
                // if there's a piece on the target square
                if (get_bit(bitboards[bb_piece], target_square))
                {
                    // remove it from corresponding bitboard
                    pop_bit(bitboards[bb_piece], target_square);
                    
                    // remove the piece from hash key
                    hash_key ^= piece_keys[bb_piece][target_square];
                    break;
                }
            }
        }
        
        // handle pawn promotions
        if (promoted_piece)
        {
            // white to move
            if (side == white)
            {
                // erase the pawn from the target square
                pop_bit(bitboards[P], target_square);
                
                // remove pawn from hash key
                hash_key ^= piece_keys[P][target_square];
            }
            
            // black to move
            else
            {
                // erase the pawn from the target square
                pop_bit(bitboards[p], target_square);
                
                // remove pawn from hash key
                hash_key ^= piece_keys[p][target_square];
            }
            
            // set up promoted piece on chess board
            set_bit(bitboards[promoted_piece], target_square);
            
            // add promoted piece into the hash key
            hash_key ^= piece_keys[promoted_piece][target_square];
        }
        
        // handle enpassant captures
        if (enpass)
        {
            // erase the pawn depending on side to move
            (side == white) ? pop_bit(bitboards[p], target_square + 8) :
                              pop_bit(bitboards[P], target_square - 8);
                              
            // white to move
            if (side == white)
            {
                // remove captured pawn
                pop_bit(bitboards[p], target_square + 8);
                
                // remove pawn from hash key
                hash_key ^= piece_keys[p][target_square + 8];
            }
            
            // black to move
            else
            {
                // remove captured pawn
                pop_bit(bitboards[P], target_square - 8);
                
                // remove pawn from hash key
                hash_key ^= piece_keys[P][target_square - 8];
            }
        }
        
        // hash enpassant if available (remove enpassant square from hash key )
        if (enpassant != no_sq) hash_key ^= enpassant_keys[enpassant];
        
        // reset enpassant square
        enpassant = no_sq;
        
        // handle double pawn push
        if (double_push)
        {
            // white to move
            if (side == white)
            {
                // set enpassant square
                enpassant = target_square + 8;
                
                // hash enpassant
                hash_key ^= enpassant_keys[target_square + 8];
            }
            
            // black to move
            else
            {
                // set enpassant square
                enpassant = target_square - 8;
                
                // hash enpassant
                hash_key ^= enpassant_keys[target_square - 8];
            }
        }
        
        // handle castling moves
        if (castling)
        {
            // switch target square
            switch (target_square)
            {
                // white castles king side
                case (g1):
                    // move H rook
                    pop_bit(bitboards[R], h1);
                    set_bit(bitboards[R], f1);
                    
                    // hash rook
                    hash_key ^= piece_keys[R][h1];  // remove rook from h1 from hash key
                    hash_key ^= piece_keys[R][f1];  // put rook on f1 into a hash key
                    break;
                
                // white castles queen side
                case (c1):
                    // move A rook
                    pop_bit(bitboards[R], a1);
                    set_bit(bitboards[R], d1);
                    
                    // hash rook
                    hash_key ^= piece_keys[R][a1];  // remove rook from a1 from hash key
                    hash_key ^= piece_keys[R][d1];  // put rook on d1 into a hash key
                    break;
                
                // black castles king side
                case (g8):
                    // move H rook
                    pop_bit(bitboards[r], h8);
                    set_bit(bitboards[r], f8);
                    
                    // hash rook
                    hash_key ^= piece_keys[r][h8];  // remove rook from h8 from hash key
                    hash_key ^= piece_keys[r][f8];  // put rook on f8 into a hash key
                    break;
                
                // black castles queen side
                case (c8):
                    // move A rook
                    pop_bit(bitboards[r], a8);
                    set_bit(bitboards[r], d8);
                    
                    // hash rook
                    hash_key ^= piece_keys[r][a8];  // remove rook from a8 from hash key
                    hash_key ^= piece_keys[r][d8];  // put rook on d8 into a hash key
                    break;
            }

            // v12: mark that this side has castled
            has_castled[side] = 1;
        }

        // hash castling
        hash_key ^= castle_keys[castle];

        // update castling rights
        castle &= castling_rights[source_square];
        castle &= castling_rights[target_square];

        // hash castling
        hash_key ^= castle_keys[castle];

        // reset occupancies
        memset(occupancies, 0ULL, 24);

        // loop over white pieces bitboards
        for (int bb_piece = P; bb_piece <= K; bb_piece++)
            // update white occupancies
            occupancies[white] |= bitboards[bb_piece];

        // loop over black pieces bitboards
        for (int bb_piece = p; bb_piece <= k; bb_piece++)
            // update black occupancies
            occupancies[black] |= bitboards[bb_piece];

        // update both sides occupancies
        occupancies[both] |= occupancies[white];
        occupancies[both] |= occupancies[black];

        // change side
        side ^= 1;

        // hash side
        hash_key ^= side_key;

        // v12: increment fullmove number after black moves
        if (side == white) fullmove_number++;
        
        // make sure that king has not been exposed into a check
        if (is_square_attacked((side == white) ? get_ls1b_index(bitboards[k]) : get_ls1b_index(bitboards[K]), side))
        {
            // take move back
            take_back();
            
            // return illegal move
            return 0;
        }
        
        // otherwise
        else
            // return legal move
            return 1;
            
            
    }
    
    // capture moves
    else
    {
        // make sure move is the capture
        if (get_move_capture(move))
            make_move(move, all_moves);
        
        // otherwise the move is not a capture
        else
            // don't make it
            return 0;
    }
}

// generate all moves
static inline void generate_moves(moves *move_list)
{
    // init move count
    move_list->count = 0;

    // define source & target squares
    int source_square, target_square;
    
    // define current piece's bitboard copy & it's attacks
    U64 bitboard, attacks;
    
    // loop over all the bitboards
    for (int piece = P; piece <= k; piece++)
    {
        // init piece bitboard copy
        bitboard = bitboards[piece];
        
        // generate white pawns & white king castling moves
        if (side == white)
        {
            // pick up white pawn bitboards index
            if (piece == P)
            {
                // loop over white pawns within white pawn bitboard
                while (bitboard)
                {
                    // init source square
                    source_square = get_ls1b_index(bitboard);
                    
                    // init target square
                    target_square = source_square - 8;
                    
                    // generate quiet pawn moves
                    if (!(target_square < a8) && !get_bit(occupancies[both], target_square))
                    {
                        // pawn promotion
                        if (source_square >= a7 && source_square <= h7)
                        {                            
                            add_move(move_list, encode_move(source_square, target_square, piece, Q, 0, 0, 0, 0));
                            add_move(move_list, encode_move(source_square, target_square, piece, R, 0, 0, 0, 0));
                            add_move(move_list, encode_move(source_square, target_square, piece, B, 0, 0, 0, 0));
                            add_move(move_list, encode_move(source_square, target_square, piece, N, 0, 0, 0, 0));
                        }
                        
                        else
                        {
                            // one square ahead pawn move
                            add_move(move_list, encode_move(source_square, target_square, piece, 0, 0, 0, 0, 0));
                            
                            // two squares ahead pawn move
                            if ((source_square >= a2 && source_square <= h2) && !get_bit(occupancies[both], target_square - 8))
                                add_move(move_list, encode_move(source_square, target_square - 8, piece, 0, 0, 1, 0, 0));
                        }
                    }
                    
                    // init pawn attacks bitboard
                    attacks = pawn_attacks[side][source_square] & occupancies[black];
                    
                    // generate pawn captures
                    while (attacks)
                    {
                        // init target square
                        target_square = get_ls1b_index(attacks);
                        
                        // pawn promotion
                        if (source_square >= a7 && source_square <= h7)
                        {
                            add_move(move_list, encode_move(source_square, target_square, piece, Q, 1, 0, 0, 0));
                            add_move(move_list, encode_move(source_square, target_square, piece, R, 1, 0, 0, 0));
                            add_move(move_list, encode_move(source_square, target_square, piece, B, 1, 0, 0, 0));
                            add_move(move_list, encode_move(source_square, target_square, piece, N, 1, 0, 0, 0));
                        }
                        
                        else
                            // one square ahead pawn move
                            add_move(move_list, encode_move(source_square, target_square, piece, 0, 1, 0, 0, 0));
                        
                        // pop ls1b of the pawn attacks
                        pop_bit(attacks, target_square);
                    }
                    
                    // generate enpassant captures
                    if (enpassant != no_sq)
                    {
                        // lookup pawn attacks and bitwise AND with enpassant square (bit)
                        U64 enpassant_attacks = pawn_attacks[side][source_square] & (1ULL << enpassant);
                        
                        // make sure enpassant capture available
                        if (enpassant_attacks)
                        {
                            // init enpassant capture target square
                            int target_enpassant = get_ls1b_index(enpassant_attacks);
                            add_move(move_list, encode_move(source_square, target_enpassant, piece, 0, 1, 0, 1, 0));
                        }
                    }
                    
                    // pop ls1b from piece bitboard copy
                    pop_bit(bitboard, source_square);
                }
            }
            
            // castling moves
            if (piece == K)
            {
                // king side castling is available
                if (castle & wk)
                {
                    // make sure square between king and king's rook are empty
                    if (!get_bit(occupancies[both], f1) && !get_bit(occupancies[both], g1))
                    {
                        // make sure king and the f1 squares are not under attacks
                        if (!is_square_attacked(e1, black) && !is_square_attacked(f1, black))
                            add_move(move_list, encode_move(e1, g1, piece, 0, 0, 0, 0, 1));
                    }
                }
                
                // queen side castling is available
                if (castle & wq)
                {
                    // make sure square between king and queen's rook are empty
                    if (!get_bit(occupancies[both], d1) && !get_bit(occupancies[both], c1) && !get_bit(occupancies[both], b1))
                    {
                        // make sure king and the d1 squares are not under attacks
                        if (!is_square_attacked(e1, black) && !is_square_attacked(d1, black))
                            add_move(move_list, encode_move(e1, c1, piece, 0, 0, 0, 0, 1));
                    }
                }
            }
        }
        
        // generate black pawns & black king castling moves
        else
        {
            // pick up black pawn bitboards index
            if (piece == p)
            {
                // loop over white pawns within white pawn bitboard
                while (bitboard)
                {
                    // init source square
                    source_square = get_ls1b_index(bitboard);
                    
                    // init target square
                    target_square = source_square + 8;
                    
                    // generate quiet pawn moves
                    if (!(target_square > h1) && !get_bit(occupancies[both], target_square))
                    {
                        // pawn promotion
                        if (source_square >= a2 && source_square <= h2)
                        {
                            add_move(move_list, encode_move(source_square, target_square, piece, q, 0, 0, 0, 0));
                            add_move(move_list, encode_move(source_square, target_square, piece, r, 0, 0, 0, 0));
                            add_move(move_list, encode_move(source_square, target_square, piece, b, 0, 0, 0, 0));
                            add_move(move_list, encode_move(source_square, target_square, piece, n, 0, 0, 0, 0));
                        }
                        
                        else
                        {
                            // one square ahead pawn move
                            add_move(move_list, encode_move(source_square, target_square, piece, 0, 0, 0, 0, 0));
                            
                            // two squares ahead pawn move
                            if ((source_square >= a7 && source_square <= h7) && !get_bit(occupancies[both], target_square + 8))
                                add_move(move_list, encode_move(source_square, target_square + 8, piece, 0, 0, 1, 0, 0));
                        }
                    }
                    
                    // init pawn attacks bitboard
                    attacks = pawn_attacks[side][source_square] & occupancies[white];
                    
                    // generate pawn captures
                    while (attacks)
                    {
                        // init target square
                        target_square = get_ls1b_index(attacks);
                        
                        // pawn promotion
                        if (source_square >= a2 && source_square <= h2)
                        {
                            add_move(move_list, encode_move(source_square, target_square, piece, q, 1, 0, 0, 0));
                            add_move(move_list, encode_move(source_square, target_square, piece, r, 1, 0, 0, 0));
                            add_move(move_list, encode_move(source_square, target_square, piece, b, 1, 0, 0, 0));
                            add_move(move_list, encode_move(source_square, target_square, piece, n, 1, 0, 0, 0));
                        }
                        
                        else
                            // one square ahead pawn move
                            add_move(move_list, encode_move(source_square, target_square, piece, 0, 1, 0, 0, 0));
                        
                        // pop ls1b of the pawn attacks
                        pop_bit(attacks, target_square);
                    }
                    
                    // generate enpassant captures
                    if (enpassant != no_sq)
                    {
                        // lookup pawn attacks and bitwise AND with enpassant square (bit)
                        U64 enpassant_attacks = pawn_attacks[side][source_square] & (1ULL << enpassant);
                        
                        // make sure enpassant capture available
                        if (enpassant_attacks)
                        {
                            // init enpassant capture target square
                            int target_enpassant = get_ls1b_index(enpassant_attacks);
                            add_move(move_list, encode_move(source_square, target_enpassant, piece, 0, 1, 0, 1, 0));
                        }
                    }
                    
                    // pop ls1b from piece bitboard copy
                    pop_bit(bitboard, source_square);
                }
            }
            
            // castling moves
            if (piece == k)
            {
                // king side castling is available
                if (castle & bk)
                {
                    // make sure square between king and king's rook are empty
                    if (!get_bit(occupancies[both], f8) && !get_bit(occupancies[both], g8))
                    {
                        // make sure king and the f8 squares are not under attacks
                        if (!is_square_attacked(e8, white) && !is_square_attacked(f8, white))
                            add_move(move_list, encode_move(e8, g8, piece, 0, 0, 0, 0, 1));
                    }
                }
                
                // queen side castling is available
                if (castle & bq)
                {
                    // make sure square between king and queen's rook are empty
                    if (!get_bit(occupancies[both], d8) && !get_bit(occupancies[both], c8) && !get_bit(occupancies[both], b8))
                    {
                        // make sure king and the d8 squares are not under attacks
                        if (!is_square_attacked(e8, white) && !is_square_attacked(d8, white))
                            add_move(move_list, encode_move(e8, c8, piece, 0, 0, 0, 0, 1));
                    }
                }
            }
        }
        
        // genarate knight moves
        if ((side == white) ? piece == N : piece == n)
        {
            // loop over source squares of piece bitboard copy
            while (bitboard)
            {
                // init source square
                source_square = get_ls1b_index(bitboard);
                
                // init piece attacks in order to get set of target squares
                attacks = knight_attacks[source_square] & ((side == white) ? ~occupancies[white] : ~occupancies[black]);
                
                // loop over target squares available from generated attacks
                while (attacks)
                {
                    // init target square
                    target_square = get_ls1b_index(attacks);    
                    
                    // quiet move
                    if (!get_bit(((side == white) ? occupancies[black] : occupancies[white]), target_square))
                        add_move(move_list, encode_move(source_square, target_square, piece, 0, 0, 0, 0, 0));
                    
                    else
                        // capture move
                        add_move(move_list, encode_move(source_square, target_square, piece, 0, 1, 0, 0, 0));
                    
                    // pop ls1b in current attacks set
                    pop_bit(attacks, target_square);
                }
                
                
                // pop ls1b of the current piece bitboard copy
                pop_bit(bitboard, source_square);
            }
        }
        
        // generate bishop moves
        if ((side == white) ? piece == B : piece == b)
        {
            // loop over source squares of piece bitboard copy
            while (bitboard)
            {
                // init source square
                source_square = get_ls1b_index(bitboard);
                
                // init piece attacks in order to get set of target squares
                attacks = get_bishop_attacks(source_square, occupancies[both]) & ((side == white) ? ~occupancies[white] : ~occupancies[black]);
                
                // loop over target squares available from generated attacks
                while (attacks)
                {
                    // init target square
                    target_square = get_ls1b_index(attacks);    
                    
                    // quiet move
                    if (!get_bit(((side == white) ? occupancies[black] : occupancies[white]), target_square))
                        add_move(move_list, encode_move(source_square, target_square, piece, 0, 0, 0, 0, 0));
                    
                    else
                        // capture move
                        add_move(move_list, encode_move(source_square, target_square, piece, 0, 1, 0, 0, 0));
                    
                    // pop ls1b in current attacks set
                    pop_bit(attacks, target_square);
                }
                
                
                // pop ls1b of the current piece bitboard copy
                pop_bit(bitboard, source_square);
            }
        }
        
        // generate rook moves
        if ((side == white) ? piece == R : piece == r)
        {
            // loop over source squares of piece bitboard copy
            while (bitboard)
            {
                // init source square
                source_square = get_ls1b_index(bitboard);
                
                // init piece attacks in order to get set of target squares
                attacks = get_rook_attacks(source_square, occupancies[both]) & ((side == white) ? ~occupancies[white] : ~occupancies[black]);
                
                // loop over target squares available from generated attacks
                while (attacks)
                {
                    // init target square
                    target_square = get_ls1b_index(attacks);    
                    
                    // quiet move
                    if (!get_bit(((side == white) ? occupancies[black] : occupancies[white]), target_square))
                        add_move(move_list, encode_move(source_square, target_square, piece, 0, 0, 0, 0, 0));
                    
                    else
                        // capture move
                        add_move(move_list, encode_move(source_square, target_square, piece, 0, 1, 0, 0, 0));
                    
                    // pop ls1b in current attacks set
                    pop_bit(attacks, target_square);
                }
                
                
                // pop ls1b of the current piece bitboard copy
                pop_bit(bitboard, source_square);
            }
        }
        
        // generate queen moves
        if ((side == white) ? piece == Q : piece == q)
        {
            // loop over source squares of piece bitboard copy
            while (bitboard)
            {
                // init source square
                source_square = get_ls1b_index(bitboard);
                
                // init piece attacks in order to get set of target squares
                attacks = get_queen_attacks(source_square, occupancies[both]) & ((side == white) ? ~occupancies[white] : ~occupancies[black]);
                
                // loop over target squares available from generated attacks
                while (attacks)
                {
                    // init target square
                    target_square = get_ls1b_index(attacks);    
                    
                    // quiet move
                    if (!get_bit(((side == white) ? occupancies[black] : occupancies[white]), target_square))
                        add_move(move_list, encode_move(source_square, target_square, piece, 0, 0, 0, 0, 0));
                    
                    else
                        // capture move
                        add_move(move_list, encode_move(source_square, target_square, piece, 0, 1, 0, 0, 0));
                    
                    // pop ls1b in current attacks set
                    pop_bit(attacks, target_square);
                }
                
                
                // pop ls1b of the current piece bitboard copy
                pop_bit(bitboard, source_square);
            }
        }

        // generate king moves
        if ((side == white) ? piece == K : piece == k)
        {
            // loop over source squares of piece bitboard copy
            while (bitboard)
            {
                // init source square
                source_square = get_ls1b_index(bitboard);
                
                // init piece attacks in order to get set of target squares
                attacks = king_attacks[source_square] & ((side == white) ? ~occupancies[white] : ~occupancies[black]);
                
                // loop over target squares available from generated attacks
                while (attacks)
                {
                    // init target square
                    target_square = get_ls1b_index(attacks);    
                    
                    // quiet move
                    if (!get_bit(((side == white) ? occupancies[black] : occupancies[white]), target_square))
                        add_move(move_list, encode_move(source_square, target_square, piece, 0, 0, 0, 0, 0));
                    
                    else
                        // capture move
                        add_move(move_list, encode_move(source_square, target_square, piece, 0, 1, 0, 0, 0));
                    
                    // pop ls1b in current attacks set
                    pop_bit(attacks, target_square);
                }

                // pop ls1b of the current piece bitboard copy
                pop_bit(bitboard, source_square);
            }
        }
    }
}


/**********************************\
 ==================================
 
               Perft
 
 ==================================
\**********************************/

// leaf nodes (number of positions reached during the test of the move generator at a given depth)
U64 nodes;

// perft driver
static inline void perft_driver(int depth)
{
    // reccursion escape condition
    if (depth == 0)
    {
        // increment nodes count (count reached positions)
        nodes++;
        return;
    }
    
    // create move list instance
    moves move_list[1];
    
    // generate moves
    generate_moves(move_list);
    
        // loop over generated moves
    for (int move_count = 0; move_count < move_list->count; move_count++)
    {   
        // preserve board state
        copy_board();
        
        // make move
        if (!make_move(move_list->moves[move_count], all_moves))
            // skip to the next move
            continue;
        
        // call perft driver recursively
        perft_driver(depth - 1);
        
        // take back
        take_back();        
    }
}

// perft test
void perft_test(int depth)
{
    printf("\n     Performance test\n\n");
    
    // create move list instance
    moves move_list[1];
    
    // generate moves
    generate_moves(move_list);
    
    // init start time
    long start = get_time_ms();
    
    // loop over generated moves
    for (int move_count = 0; move_count < move_list->count; move_count++)
    {   
        // preserve board state
        copy_board();
        
        // make move
        if (!make_move(move_list->moves[move_count], all_moves))
            // skip to the next move
            continue;
        
        // cummulative nodes
        long cummulative_nodes = nodes;
        
        // call perft driver recursively
        perft_driver(depth - 1);
        
        // old nodes
        long old_nodes = nodes - cummulative_nodes;
        
        // take back
        take_back();
        
        // print move
        printf("     move: %s%s%c  nodes: %ld\n", square_to_coordinates[get_move_source(move_list->moves[move_count])],
                                                  square_to_coordinates[get_move_target(move_list->moves[move_count])],
                                                  get_move_promoted(move_list->moves[move_count]) ? promoted_pieces[get_move_promoted(move_list->moves[move_count])] : ' ',
                                                  old_nodes);
    }
    
    // print results
    printf("\n    Depth: %d\n", depth);
    printf("    Nodes: %lld\n", nodes);
    printf("     Time: %ld\n\n", get_time_ms() - start);
}


/**********************************\
 ==================================

       BBC Evaluation Masks
   (needed by v13 evaluation)

 ==================================
\**********************************/

// mirror positional score tables for opposite side
const int mirror_score[128] =
{
	a1, b1, c1, d1, e1, f1, g1, h1,
	a2, b2, c2, d2, e2, f2, g2, h2,
	a3, b3, c3, d3, e3, f3, g3, h3,
	a4, b4, c4, d4, e4, f4, g4, h4,
	a5, b5, c5, d5, e5, f5, g5, h5,
	a6, b6, c6, d6, e6, f6, g6, h6,
	a7, b7, c7, d7, e7, f7, g7, h7,
	a8, b8, c8, d8, e8, f8, g8, h8
};

// file masks [square]
U64 file_masks[64];

// rank masks [square]
U64 rank_masks[64];

// isolated pawn masks [square]
U64 isolated_masks[64];

// white passed pawn masks [square]
U64 white_passed_masks[64];

// black passed pawn masks [square]
U64 black_passed_masks[64];

// extract rank from a square [square]
const int get_rank[64] =
{
    7, 7, 7, 7, 7, 7, 7, 7,
    6, 6, 6, 6, 6, 6, 6, 6,
    5, 5, 5, 5, 5, 5, 5, 5,
    4, 4, 4, 4, 4, 4, 4, 4,
    3, 3, 3, 3, 3, 3, 3, 3,
    2, 2, 2, 2, 2, 2, 2, 2,
    1, 1, 1, 1, 1, 1, 1, 1,
	0, 0, 0, 0, 0, 0, 0, 0
};

// set file or rank mask
U64 set_file_rank_mask(int file_number, int rank_number)
{
    U64 mask = 0ULL;
    for (int rank = 0; rank < 8; rank++)
    {
        for (int file = 0; file < 8; file++)
        {
            int square = rank * 8 + file;
            if (file_number != -1)
            {
                if (file == file_number)
                    mask |= set_bit(mask, square);
            }
            else if (rank_number != -1)
            {
                if (rank == rank_number)
                    mask |= set_bit(mask, square);
            }
        }
    }
    return mask;
}

// init evaluation masks
void init_evaluation_masks()
{
    for (int rank = 0; rank < 8; rank++)
    {
        for (int file = 0; file < 8; file++)
        {
            int square = rank * 8 + file;
            file_masks[square] |= set_file_rank_mask(file, -1);
        }
    }

    for (int rank = 0; rank < 8; rank++)
    {
        for (int file = 0; file < 8; file++)
        {
            int square = rank * 8 + file;
            rank_masks[square] |= set_file_rank_mask(-1, rank);
        }
    }

    for (int rank = 0; rank < 8; rank++)
    {
        for (int file = 0; file < 8; file++)
        {
            int square = rank * 8 + file;
            isolated_masks[square] |= set_file_rank_mask(file - 1, -1);
            isolated_masks[square] |= set_file_rank_mask(file + 1, -1);
        }
    }

    for (int rank = 0; rank < 8; rank++)
    {
        for (int file = 0; file < 8; file++)
        {
            int square = rank * 8 + file;
            white_passed_masks[square] |= set_file_rank_mask(file - 1, -1);
            white_passed_masks[square] |= set_file_rank_mask(file, -1);
            white_passed_masks[square] |= set_file_rank_mask(file + 1, -1);
            for (int i = 0; i < (8 - rank); i++)
                white_passed_masks[square] &= ~rank_masks[(7 - i) * 8 + file];
        }
    }

    for (int rank = 0; rank < 8; rank++)
    {
        for (int file = 0; file < 8; file++)
        {
            int square = rank * 8 + file;
            black_passed_masks[square] |= set_file_rank_mask(file - 1, -1);
            black_passed_masks[square] |= set_file_rank_mask(file, -1);
            black_passed_masks[square] |= set_file_rank_mask(file + 1, -1);
            for (int i = 0; i < rank + 1; i++)
                black_passed_masks[square] &= ~rank_masks[i * 8 + file];
        }
    }
}


/**********************************\
 ==================================

      v13 Evaluation (from v12.py)
      Tapered eval with PSTs

 ==================================
\**********************************/

// v13 piece values in centipawns [P, N, B, R, Q, K, p, n, b, r, q, k]
const int v13_piece_values[12] = {
    100, 300, 300, 500, 900, 0,
   -100,-300,-300,-500,-900, 0
};

// Game phase weights per piece type: N=1, B=1, R=2, Q=4
#define TOTAL_PHASE 24
#define PHASE_THRESHOLD 7  // ~0.3 * 24

// PSTs for white pieces in BBC square order (a8=0, row 0 = rank 8)
// Converted from v12.py: rows reversed, values * 100

// Pawn middlegame PST
const int pst_pawn_mg[64] = {
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 35, 35, 20, 10, 10,
     5,  5, 10, 30, 30, 10,  5,  5,
     0,  0,  0, 25, 25,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
};

// Pawn endgame PST
const int pst_pawn_eg[64] = {
     0,  0,  0,  0,  0,  0,  0,  0,
    80, 80, 80, 80, 80, 80, 80, 80,
    50, 50, 50, 50, 50, 50, 50, 50,
    30, 30, 30, 30, 30, 30, 30, 30,
    20, 20, 20, 20, 20, 20, 20, 20,
    10, 10, 10, 10, 10, 10, 10, 10,
     0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,
};

// Knight PST (shared MG/EG)
const int pst_knight[64] = {
   -50,-40,-30,-30,-30,-30,-40,-50,
   -40,-20,  0,  5,  5,  0,-20,-40,
   -30,  5, 10, 15, 15, 10,  5,-30,
   -30,  0, 15, 20, 20, 15,  0,-30,
   -30,  5, 15, 20, 20, 15,  5,-30,
   -30,  0, 10, 15, 15, 10,  0,-30,
   -40,-20,  0,  0,  0,  0,-20,-40,
   -50,-40,-30,-30,-30,-30,-40,-50,
};

// Bishop PST (shared MG/EG)
const int pst_bishop[64] = {
   -20,-10,-10,-10,-10,-10,-10,-20,
   -10,  5,  0,  0,  0,  0,  5,-10,
   -10, 10, 10, 10, 10, 10, 10,-10,
   -10,  0, 10, 10, 10, 10,  0,-10,
   -10,  5,  5, 10, 10,  5,  5,-10,
   -10,  0,  5, 10, 10,  5,  0,-10,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -20,-10,-10,-10,-10,-10,-10,-20,
};

// Rook PST (shared MG/EG)
const int pst_rook[64] = {
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     0,  0,  0,  5,  5,  0,  0,  0,
};

// Queen PST (shared MG/EG)
const int pst_queen[64] = {
   -20,-10,-10, -5, -5,-10,-10,-20,
   -10,  0,  5,  0,  0,  0,  0,-10,
   -10,  5,  5,  5,  5,  5,  0,-10,
     0,  0,  5,  5,  5,  5,  0, -5,
    -5,  0,  5,  5,  5,  5,  0, -5,
   -10,  0,  5,  5,  5,  5,  0,-10,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -20,-10,-10, -5, -5,-10,-10,-20,
};

// King middlegame PST
const int pst_king_mg[64] = {
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -20,-30,-30,-40,-40,-30,-30,-20,
   -10,-20,-20,-20,-20,-20,-20,-10,
    20, 20,  0,  0,  0,  0, 20, 20,
    20, 30, 10,  0,  0, 10, 30, 20,
};

// King endgame PST
const int pst_king_eg[64] = {
   -50,-30,-30,-30,-30,-30,-30,-50,
   -30,-10,  0,  0,  0,  0,-10,-30,
   -30,  0, 10, 15, 15, 10,  0,-30,
   -30,  0, 15, 20, 20, 15,  0,-30,
   -30,  0, 15, 20, 20, 15,  0,-30,
   -30,  0, 10, 15, 15, 10,  0,-30,
   -30,-10,  0,  0,  0,  0,-10,-30,
   -50,-30,-30,-30,-30,-30,-30,-50,
};

// Precomputed integer sqrt*20 table for mobility scoring
// isqrt_x20[n] = (int)(20.0 * sqrt(n))
const int isqrt_x20[32] = {
     0, 20, 28, 34, 40, 44, 48, 52, 56, 60, 63, 66, 69, 72, 74, 77,
    80, 82, 84, 87, 89, 91, 93, 95, 97, 100,101,103,105,107,109,111
};

// BBC get_rank: maps square to rank (a8=0 → rank 7, a1=56 → rank 0)
// Already defined in BBC as get_rank[64]
// For white advancement: rank = 7 - get_rank[sq] (rank 0 at bottom, 7 at top)
// For black advancement: rank = get_rank[sq]

// Calculate game phase (0-24)
static inline int get_game_phase()
{
    int phase = 0;
    // Knights: weight 1
    phase += count_bits(bitboards[N]) + count_bits(bitboards[n]);
    // Bishops: weight 1
    phase += count_bits(bitboards[B]) + count_bits(bitboards[b]);
    // Rooks: weight 2
    phase += 2 * (count_bits(bitboards[R]) + count_bits(bitboards[r]));
    // Queens: weight 4
    phase += 4 * (count_bits(bitboards[Q]) + count_bits(bitboards[q]));
    if (phase > TOTAL_PHASE) phase = TOTAL_PHASE;
    return phase;
}

// Evaluate one side's material + positional score
static inline int evaluate_side(int color, int phase)
{
    int score = 0;
    int end_game = (phase < PHASE_THRESHOLD);
    int bishop_count = 0;
    int pawn_files[8] = {0};  // count of pawns per file
    int pawn_file_mask = 0;   // bitmask of files with pawns

    // Piece indices for this side
    int pawn_piece   = (color == white) ? P : p;
    int knight_piece = (color == white) ? N : n;
    int bishop_piece = (color == white) ? B : b;
    int rook_piece   = (color == white) ? R : r;
    int queen_piece  = (color == white) ? Q : q;
    int king_piece   = (color == white) ? K : k;
    int enemy_pawn   = (color == white) ? p : P;

    U64 bb, occ_all = occupancies[both];

    // === PAWNS ===
    bb = bitboards[pawn_piece];
    while (bb) {
        int sq = get_ls1b_index(bb);
        int wsq = (color == white) ? sq : mirror_score[sq];

        // Material
        score += 100;

        // Tapered PST
        score += (pst_pawn_mg[wsq] * phase + pst_pawn_eg[wsq] * (TOTAL_PHASE - phase)) / TOTAL_PHASE;

        // Pawn structure tracking
        int file = sq & 7;
        pawn_files[file]++;
        pawn_file_mask |= (1 << file);

        // Passed pawn check
        U64 *pass_masks = (color == white) ? white_passed_masks : black_passed_masks;
        if ((pass_masks[sq] & bitboards[enemy_pawn]) == 0) {
            // Advancement: for white, higher rank = more advanced
            // BBC get_rank: a8=rank7, a1=rank0. For white pawn, advancement = 7 - get_rank[sq]
            int advancement = (color == white) ? (7 - get_rank[sq]) : get_rank[sq];
            int pass_bonus_mg = 50 * advancement / 6;
            int pass_bonus_eg = 100 * advancement / 6;
            score += (pass_bonus_mg * phase + pass_bonus_eg * (TOTAL_PHASE - phase)) / TOTAL_PHASE;
        }

        pop_bit(bb, sq);
    }

    // === KNIGHTS ===
    bb = bitboards[knight_piece];
    while (bb) {
        int sq = get_ls1b_index(bb);
        int wsq = (color == white) ? sq : mirror_score[sq];
        score += 300;
        score += pst_knight[wsq];
        // Mobility
        int mob = count_bits(knight_attacks[sq] & ~occupancies[color]);
        if (mob < 32) score += isqrt_x20[mob];
        pop_bit(bb, sq);
    }

    // === BISHOPS ===
    bb = bitboards[bishop_piece];
    while (bb) {
        int sq = get_ls1b_index(bb);
        int wsq = (color == white) ? sq : mirror_score[sq];
        score += 300;
        score += pst_bishop[wsq];
        bishop_count++;
        // Mobility
        int mob = count_bits(get_bishop_attacks(sq, occ_all) & ~occupancies[color]);
        if (mob < 32) score += isqrt_x20[mob];
        pop_bit(bb, sq);
    }

    // === ROOKS ===
    bb = bitboards[rook_piece];
    while (bb) {
        int sq = get_ls1b_index(bb);
        int wsq = (color == white) ? sq : mirror_score[sq];
        score += 500;
        score += pst_rook[wsq];
        // Mobility
        int mob = count_bits(get_rook_attacks(sq, occ_all) & ~occupancies[color]);
        if (mob < 32) score += isqrt_x20[mob];
        pop_bit(bb, sq);
    }

    // === QUEENS ===
    bb = bitboards[queen_piece];
    while (bb) {
        int sq = get_ls1b_index(bb);
        int wsq = (color == white) ? sq : mirror_score[sq];
        score += 900;
        score += pst_queen[wsq];
        // Mobility
        int mob = count_bits(get_queen_attacks(sq, occ_all) & ~occupancies[color]);
        if (mob < 32) score += isqrt_x20[mob];
        pop_bit(bb, sq);
    }

    // === KING ===
    {
        int sq = get_ls1b_index(bitboards[king_piece]);
        int wsq = (color == white) ? sq : mirror_score[sq];
        // Tapered king PST
        score += (pst_king_mg[wsq] * phase + pst_king_eg[wsq] * (TOTAL_PHASE - phase)) / TOTAL_PHASE;

        // King safety (middlegame only, phase >= threshold)
        if (!end_game) {
            int shield = count_bits(king_attacks[sq] & bitboards[pawn_piece]);
            score += 15 * shield;
        }

        // King endgame bonuses
        if (end_game) {
            int rank = sq >> 3;  // BBC: 0-7
            int file = sq & 7;
            // Centralization: distance from center (3.5, 3.5)
            int rank_dist = rank > 3 ? rank - 3 : 4 - rank;  // approx abs(rank - 3.5)
            int file_dist = file > 3 ? file - 3 : 4 - file;
            int center_dist = rank_dist > file_dist ? rank_dist : file_dist;
            score -= center_dist * 10;

            // King proximity to enemy king
            int enemy_king_sq = get_ls1b_index(bitboards[(color == white) ? k : K]);
            int er = enemy_king_sq >> 3, ef = enemy_king_sq & 7;
            int rdist = rank > er ? rank - er : er - rank;
            int fdist = file > ef ? file - ef : ef - file;
            int dist = rdist > fdist ? rdist : fdist;
            score -= dist * 5;
        }
    }

    // === Bishop pair bonus ===
    if (bishop_count >= 2)
        score += 30;

    // === Doubled pawns penalty ===
    for (int f = 0; f < 8; f++) {
        if (pawn_files[f] >= 2)
            score -= 30 * (pawn_files[f] - 1);
    }

    // === Isolated pawns penalty ===
    for (int f = 0; f < 8; f++) {
        if (pawn_files[f] > 0) {
            int has_neighbor = 0;
            if (f > 0 && (pawn_file_mask & (1 << (f - 1)))) has_neighbor = 1;
            if (f < 7 && (pawn_file_mask & (1 << (f + 1)))) has_neighbor = 1;
            if (!has_neighbor)
                score -= 20 * pawn_files[f];
        }
    }

    // === Castling bonuses ===
    // +10cp per castling right retained
    if (color == white) {
        if (castle & wk) score += 10;
        if (castle & wq) score += 10;
    } else {
        if (castle & bk) score += 10;
        if (castle & bq) score += 10;
    }

    // +40cp if actually castled
    if (has_castled[color])
        score += 40;

    return score;
}

// Main evaluation function (returns score from side-to-move perspective)
static inline int evaluate()
{
    int phase = get_game_phase();
    int white_score = evaluate_side(white, phase);
    int black_score = evaluate_side(black, phase);
    int score = white_score - black_score;
    return (side == white) ? score : -score;
}


// Score bounds for mating scores
#define infinity 50000
#define mate_value 49000
#define mate_score 48000

/**********************************\
 ==================================

        v13 Transposition Table

 ==================================
\**********************************/

// TT size: 2M entries (power of 2)
#define TT_SIZE (1 << 21)  // 2097152
#define TT_MASK (TT_SIZE - 1)

#define NO_HASH_ENTRY 100000

#define HASH_FLAG_EXACT 0
#define HASH_FLAG_ALPHA 1  // UPPERBOUND
#define HASH_FLAG_BETA  2  // LOWERBOUND

typedef struct {
    U64 hash_key;
    int depth;
    int score;
    int flag;
    int best_move;
} tt_entry;

tt_entry hash_table[TT_SIZE];

void clear_hash_table()
{
    memset(hash_table, 0, sizeof(hash_table));
}

// Read TT entry; returns NO_HASH_ENTRY if not found
// Also sets *tt_best_move if entry exists for this position
static inline int read_hash_entry(int alpha, int beta, int depth, int *tt_best_move)
{
    tt_entry *entry = &hash_table[hash_key & TT_MASK];

    if (entry->hash_key == hash_key) {
        // Always extract best move regardless of depth
        *tt_best_move = entry->best_move;

        if (entry->depth >= depth) {
            int score = entry->score;

            // Adjust mate scores for search path
            if (score < -mate_score) score += ply;
            if (score > mate_score) score -= ply;

            if (entry->flag == HASH_FLAG_EXACT)
                return score;
            if (entry->flag == HASH_FLAG_ALPHA && score <= alpha)
                return alpha;
            if (entry->flag == HASH_FLAG_BETA && score >= beta)
                return beta;
        }
    }

    return NO_HASH_ENTRY;
}

// Write TT entry (depth-preferred replacement)
static inline void write_hash_entry(int score, int depth, int flag, int best_move)
{
    tt_entry *entry = &hash_table[hash_key & TT_MASK];

    // Depth-preferred: only overwrite if new depth >= stored depth, or different position
    if (entry->hash_key != hash_key || depth >= entry->depth) {
        // Adjust mate scores for storage
        if (score < -mate_score) score -= ply;
        if (score > mate_score) score += ply;

        entry->hash_key = hash_key;
        entry->depth = depth;
        entry->score = score;
        entry->flag = flag;
        entry->best_move = best_move;
    }
}


/**********************************\
 ==================================

             v13 Search

 ==================================
\**********************************/

// MVV-LVA table [attacker][victim]
static int mvv_lva[12][12] = {
    105, 205, 305, 405, 505, 605,  105, 205, 305, 405, 505, 605,
    104, 204, 304, 404, 504, 604,  104, 204, 304, 404, 504, 604,
    103, 203, 303, 403, 503, 603,  103, 203, 303, 403, 503, 603,
    102, 202, 302, 402, 502, 602,  102, 202, 302, 402, 502, 602,
    101, 201, 301, 401, 501, 601,  101, 201, 301, 401, 501, 601,
    100, 200, 300, 400, 500, 600,  100, 200, 300, 400, 500, 600,

    105, 205, 305, 405, 505, 605,  105, 205, 305, 405, 505, 605,
    104, 204, 304, 404, 504, 604,  104, 204, 304, 404, 504, 604,
    103, 203, 303, 403, 503, 603,  103, 203, 303, 403, 503, 603,
    102, 202, 302, 402, 502, 602,  102, 202, 302, 402, 502, 602,
    101, 201, 301, 401, 501, 601,  101, 201, 301, 401, 501, 601,
    100, 200, 300, 400, 500, 600,  100, 200, 300, 400, 500, 600
};

#define max_ply 64

// Killer moves [id][ply]
int killer_moves[2][max_ply];

// History moves [piece][square]
int history_moves[12][64];

// PV table
int pv_length[max_ply];
int pv_table[max_ply][max_ply];

// Pre-computed LMR reduction table
int lmr_table[64][64];

// Futility margins indexed by depth (centipawns)
const int futility_margins[3] = {0, 150, 350};

// Time control globals
int v13_time_budget_ms = 0;    // allocated time for this move in ms
long v13_search_start = 0;     // start time in ms
int v13_stopped = 0;           // time-up flag
#define TIME_CHECK_INTERVAL 2048

// Initialize LMR table
void init_lmr_table()
{
    for (int d = 1; d < 64; d++)
        for (int m = 1; m < 64; m++)
            lmr_table[d][m] = (int)(1.0 + log(d) * log(m) / 2.5);
}

// Check if we should stop searching
static inline void check_time()
{
    if (v13_time_budget_ms > 0) {
        long elapsed = get_time_ms() - v13_search_start;
        if (elapsed > (long)(v13_time_budget_ms * 0.8))
            v13_stopped = 1;
    }
}

// Is current position in check?
static inline int is_in_check()
{
    if (side == white)
        return is_square_attacked(get_ls1b_index(bitboards[K]), black);
    else
        return is_square_attacked(get_ls1b_index(bitboards[k]), white);
}

// Repetition detection
static inline int is_repetition()
{
    for (int i = 0; i < repetition_index; i++)
        if (repetition_table[i] == hash_key)
            return 1;
    return 0;
}

// Score a move for ordering
// Priority: TT move (2M) > captures MVV-LVA (10000+) > killer (9000/8000) > history
static inline int score_move(int move, int tt_move)
{
    // TT move gets highest priority
    if (move == tt_move)
        return 2000000;

    // Captures: MVV-LVA + 10000 base
    if (get_move_capture(move)) {
        int target_piece = P;
        int start_piece = (side == white) ? p : P;
        int end_piece = (side == white) ? k : K;

        for (int bb_piece = start_piece; bb_piece <= end_piece; bb_piece++) {
            if (get_bit(bitboards[bb_piece], get_move_target(move))) {
                target_piece = bb_piece;
                break;
            }
        }
        return mvv_lva[get_move_piece(move)][target_piece] + 1000000;
    }

    // Killer moves
    if (killer_moves[0][ply] == move) return 900000;
    if (killer_moves[1][ply] == move) return 800000;

    // History heuristic
    return history_moves[get_move_piece(move)][get_move_target(move)];
}

// Sort moves by score (selection sort for simplicity)
static inline void sort_moves(moves *move_list, int tt_move)
{
    int move_scores[256];
    for (int i = 0; i < move_list->count; i++)
        move_scores[i] = score_move(move_list->moves[i], tt_move);

    for (int i = 0; i < move_list->count; i++) {
        for (int j = i + 1; j < move_list->count; j++) {
            if (move_scores[i] < move_scores[j]) {
                // Swap scores
                int tmp = move_scores[i];
                move_scores[i] = move_scores[j];
                move_scores[j] = tmp;
                // Swap moves
                tmp = move_list->moves[i];
                move_list->moves[i] = move_list->moves[j];
                move_list->moves[j] = tmp;
            }
        }
    }
}

// Quiescence search
static inline int quiescence(int alpha, int beta)
{
    // Time check
    if ((nodes & (TIME_CHECK_INTERVAL - 1)) == 0)
        check_time();

    if (v13_stopped) return 0;

    nodes++;

    if (ply > max_ply - 1)
        return evaluate();

    int stand_pat = evaluate();

    if (stand_pat >= beta)
        return beta;

    // Delta pruning: if stand_pat + queen value can't raise alpha, prune
    if (stand_pat + 900 < alpha)
        return alpha;

    if (stand_pat > alpha)
        alpha = stand_pat;

    // Generate all moves, filter to captures only
    moves move_list[1];
    generate_moves(move_list);
    sort_moves(move_list, 0);

    for (int count = 0; count < move_list->count; count++) {
        copy_board();
        ply++;
        repetition_index++;
        repetition_table[repetition_index] = hash_key;

        // Only search captures (and promotions via only_captures flag)
        if (make_move(move_list->moves[count], only_captures) == 0) {
            ply--;
            repetition_index--;
            continue;
        }

        int score = -quiescence(-beta, -alpha);

        ply--;
        repetition_index--;
        take_back();

        if (v13_stopped) return 0;

        if (score > alpha) {
            alpha = score;
            if (score >= beta)
                return beta;
        }
    }

    return alpha;
}

// Negamax with alpha-beta, TT, null move, LMR, PVS, futility pruning
static inline int negamax(int alpha, int beta, int depth, int null_ok)
{
    // Time check
    if ((nodes & (TIME_CHECK_INTERVAL - 1)) == 0)
        check_time();

    if (v13_stopped) return 0;

    // Init PV length
    pv_length[ply] = ply;

    // Repetition detection
    if (ply && is_repetition())
        return 0;

    // PV node flag
    int pv_node = (beta - alpha > 1);

    // TT lookup
    int tt_best_move = 0;
    if (ply) {
        int tt_score = read_hash_entry(alpha, beta, depth, &tt_best_move);
        if (tt_score != NO_HASH_ENTRY && !pv_node)
            return tt_score;
    }

    int in_check = is_in_check();

    // Check extension
    if (in_check && ply < max_ply - 5)
        depth++;

    // Drop to quiescence at depth 0
    if (depth <= 0)
        return quiescence(alpha, beta);

    // Max ply overflow
    if (ply > max_ply - 1)
        return evaluate();

    nodes++;

    // Null move pruning
    int game_phase = get_game_phase();
    if (null_ok && !in_check && game_phase >= PHASE_THRESHOLD && depth >= 3 && ply) {
        copy_board();
        ply++;
        repetition_index++;
        repetition_table[repetition_index] = hash_key;

        // Hash out en passant
        if (enpassant != no_sq) hash_key ^= enpassant_keys[enpassant];
        enpassant = no_sq;

        // Switch side
        side ^= 1;
        hash_key ^= side_key;

        int null_score = -negamax(-beta, -beta + 1, depth - 1 - 3, 0);

        ply--;
        repetition_index--;
        take_back();

        if (v13_stopped) return 0;

        if (null_score >= beta)
            return beta;
    }

    // Futility pruning setup
    int futile = 0;
    if (depth <= 2 && !in_check && alpha > -mate_score && alpha < mate_score) {
        int static_eval = evaluate();
        if (static_eval + futility_margins[depth] <= alpha)
            futile = 1;
    }

    // Generate and sort moves
    moves move_list[1];
    generate_moves(move_list);
    sort_moves(move_list, tt_best_move);

    int legal_moves_count = 0;
    int best_score = -infinity;
    int best_move = 0;
    int hash_flag = HASH_FLAG_ALPHA;

    for (int count = 0; count < move_list->count; count++) {
        int move = move_list->moves[count];
        int is_capture = get_move_capture(move);
        int is_promotion = get_move_promoted(move);

        // Futility pruning: skip quiet moves in futile positions
        if (futile && legal_moves_count > 0 && !is_capture && !is_promotion)
            continue;

        copy_board();
        ply++;
        repetition_index++;
        repetition_table[repetition_index] = hash_key;

        if (make_move(move, all_moves) == 0) {
            ply--;
            repetition_index--;
            continue;
        }

        legal_moves_count++;

        int score;

        // PVS with LMR
        if (legal_moves_count == 1) {
            // First move: full window search
            score = -negamax(-beta, -alpha, depth - 1, 1);
        } else {
            // LMR: reduce depth for late quiet moves
            int reduction = 0;
            if (legal_moves_count >= 4 && depth >= 3 && !in_check && !is_capture && !is_promotion) {
                int idx = legal_moves_count < 64 ? legal_moves_count : 63;
                reduction = lmr_table[depth < 64 ? depth : 63][idx];
                if (reduction > depth - 2) reduction = depth - 2;
                // Don't reduce if move gives check
                if (is_in_check()) reduction = 0;
            }

            // Null window search with reduction
            score = -negamax(-alpha - 1, -alpha, depth - 1 - reduction, 1);

            // Re-search if it beats alpha
            if (!v13_stopped && score > alpha && (reduction > 0 || score < beta))
                score = -negamax(-beta, -alpha, depth - 1, 1);
        }

        ply--;
        repetition_index--;
        take_back();

        if (v13_stopped) return 0;

        if (score > best_score) {
            best_score = score;
            best_move = move;

            if (score > alpha) {
                hash_flag = HASH_FLAG_EXACT;
                alpha = score;

                // Store history for quiet moves
                if (!is_capture)
                    history_moves[get_move_piece(move)][get_move_target(move)] += depth * depth;

                // Write PV
                pv_table[ply][ply] = move;
                for (int next_ply = ply + 1; next_ply < pv_length[ply + 1]; next_ply++)
                    pv_table[ply][next_ply] = pv_table[ply + 1][next_ply];
                pv_length[ply] = pv_length[ply + 1];

                if (score >= beta) {
                    // Store TT entry
                    write_hash_entry(beta, depth, HASH_FLAG_BETA, best_move);

                    // Killer moves for quiet moves
                    if (!is_capture) {
                        killer_moves[1][ply] = killer_moves[0][ply];
                        killer_moves[0][ply] = move;
                    }

                    return beta;
                }
            }
        }
    }

    // No legal moves: checkmate or stalemate
    if (legal_moves_count == 0) {
        if (in_check)
            return -mate_value + ply;
        else
            return 0;
    }

    // Store TT entry
    write_hash_entry(alpha, depth, hash_flag, best_move);

    return alpha;
}

// Time management: allocate time for this move (in ms)
static int allocate_time(int my_time_ms, int my_inc_ms, int move_number)
{
    int moves_left;
    if (move_number < 10) moves_left = 40;
    else if (move_number < 30) moves_left = 30;
    else moves_left = 20;

    int base = my_time_ms / moves_left;
    base += (int)(my_inc_ms * 0.8);

    int max_time = my_time_ms / 5;
    int min_time = my_time_ms / 20;
    if (min_time > 500) min_time = 500;

    int budget = base;
    if (budget > max_time) budget = max_time;
    if (budget < min_time) budget = min_time;

    return budget;
}

// Search position: iterative deepening with aspiration windows
void search_position(int max_depth, int time_budget_ms)
{
    // Reset
    nodes = 0;
    v13_stopped = 0;
    v13_search_start = get_time_ms();
    v13_time_budget_ms = time_budget_ms;

    memset(killer_moves, 0, sizeof(killer_moves));
    memset(history_moves, 0, sizeof(history_moves));
    memset(pv_table, 0, sizeof(pv_table));
    memset(pv_length, 0, sizeof(pv_length));

    int score = 0;
    int alpha = -infinity;
    int beta = infinity;

    int game_phase = get_game_phase();

    // Minimum depth based on time budget
    int min_depth;
    if (time_budget_ms <= 0) min_depth = max_depth;
    else if (time_budget_ms < 2000) min_depth = 3;
    else if (time_budget_ms < 5000) min_depth = 4;
    else min_depth = 5;

    for (int current_depth = 1; current_depth <= max_depth; current_depth++) {
        // Time check: don't start new depth if 40%+ of budget used
        if (time_budget_ms > 0 && current_depth > min_depth) {
            long elapsed = get_time_ms() - v13_search_start;
            if (elapsed > (long)(time_budget_ms * 0.4))
                break;
        }

        v13_stopped = 0;

        // Endgame extension: search 1 ply deeper when few pieces remain
        int search_depth = (game_phase < PHASE_THRESHOLD) ? current_depth + 1 : current_depth;

        // Aspiration windows
        if (current_depth <= 2) {
            alpha = -infinity;
            beta = infinity;
        } else {
            alpha = score - 50;
            beta = score + 50;
        }

        score = negamax(alpha, beta, search_depth, 1);

        // Aspiration window fail: re-search with full window
        if (!v13_stopped && (score <= alpha || score >= beta)) {
            // Check if we have time for re-search
            if (time_budget_ms > 0) {
                long elapsed = get_time_ms() - v13_search_start;
                if (elapsed > (long)(time_budget_ms * 0.5)) {
                    // Not enough time, use the result we have
                    // (pv_table may have been partially updated)
                    if (pv_length[0] > 0)
                        goto done;
                }
            }
            alpha = -infinity;
            beta = infinity;
            score = negamax(alpha, beta, search_depth, 1);
        }

        if (v13_stopped) break;

        // Print UCI info
        long elapsed = get_time_ms() - v13_search_start;
        if (elapsed < 1) elapsed = 1;

        if (score > -mate_value && score < -mate_score)
            printf("info score mate %d depth %d nodes %lld time %ld pv ",
                   -(score + mate_value) / 2 - 1, current_depth, nodes, elapsed);
        else if (score > mate_score && score < mate_value)
            printf("info score mate %d depth %d nodes %lld time %ld pv ",
                   (mate_value - score) / 2 + 1, current_depth, nodes, elapsed);
        else
            printf("info score cp %d depth %d nodes %lld time %ld pv ",
                   score, current_depth, nodes, elapsed);

        for (int i = 0; i < pv_length[0]; i++) {
            print_move(pv_table[0][i]);
            printf(" ");
        }
        printf("\n");
        fflush(stdout);

        // Stop if mate found
        if (score > mate_score || score < -mate_score)
            break;

        // Set up aspiration for next iteration
        // (alpha/beta will be reset at top of loop if needed)
    }

done:
    // Print best move
    printf("bestmove ");
    if (pv_length[0] > 0)
        print_move(pv_table[0][0]);
    else
        printf("0000");
    printf("\n");
    fflush(stdout);
}


/**********************************\
 ==================================

              v13 UCI

 ==================================
\**********************************/

// Parse user/GUI move string input (e.g. "e7e8q")
int parse_move(char *move_string)
{
    moves move_list[1];
    generate_moves(move_list);

    int source_square = (move_string[0] - 'a') + (8 - (move_string[1] - '0')) * 8;
    int target_square = (move_string[2] - 'a') + (8 - (move_string[3] - '0')) * 8;

    for (int count = 0; count < move_list->count; count++) {
        int move = move_list->moves[count];

        if (source_square == get_move_source(move) && target_square == get_move_target(move)) {
            int promoted = get_move_promoted(move);

            if (promoted) {
                if ((promoted == Q || promoted == q) && move_string[4] == 'q') return move;
                if ((promoted == R || promoted == r) && move_string[4] == 'r') return move;
                if ((promoted == B || promoted == b) && move_string[4] == 'b') return move;
                if ((promoted == N || promoted == n) && move_string[4] == 'n') return move;
                continue;
            }

            return move;
        }
    }

    return 0;
}

// Parse UCI "position" command
void parse_position(char *command)
{
    command += 9;
    char *current_char = command;

    if (strncmp(command, "startpos", 8) == 0)
        parse_fen(start_position);
    else {
        current_char = strstr(command, "fen");
        if (current_char == NULL)
            parse_fen(start_position);
        else {
            current_char += 4;
            parse_fen(current_char);
        }
    }

    // Parse moves
    current_char = strstr(command, "moves");
    if (current_char != NULL) {
        current_char += 6;

        while (*current_char) {
            int move = parse_move(current_char);
            if (move == 0) break;

            repetition_index++;
            repetition_table[repetition_index] = hash_key;

            make_move(move, all_moves);

            while (*current_char && *current_char != ' ') current_char++;
            current_char++;
        }
    }
}

// Parse UCI "go" command with v13's time management
void parse_go(char *command)
{
    int depth = -1;
    int wtime = -1, btime = -1, winc = 0, binc = 0;
    int movetime = -1;
    char *argument = NULL;

    if ((argument = strstr(command, "depth")))
        depth = atoi(argument + 6);

    if ((argument = strstr(command, "wtime")))
        wtime = atoi(argument + 6);

    if ((argument = strstr(command, "btime")))
        btime = atoi(argument + 6);

    if ((argument = strstr(command, "winc")))
        winc = atoi(argument + 5);

    if ((argument = strstr(command, "binc")))
        binc = atoi(argument + 5);

    if ((argument = strstr(command, "movetime")))
        movetime = atoi(argument + 9);

    int time_budget_ms = 0;
    int search_depth = 30;

    if (depth != -1) {
        // Fixed depth search
        search_depth = depth;
        time_budget_ms = 0;
    } else if (movetime != -1) {
        // Fixed time per move
        time_budget_ms = movetime;
        search_depth = 30;
    } else {
        // Time control: use v13's allocate_time
        int my_time = (side == white) ? wtime : btime;
        int my_inc = (side == white) ? winc : binc;

        if (my_time > 0) {
            time_budget_ms = allocate_time(my_time, my_inc, fullmove_number);
            search_depth = 30;
        } else {
            // Infinite or no time info
            search_depth = 30;
            time_budget_ms = 0;
        }
    }

    search_position(search_depth, time_budget_ms);
}

// Opening book: simple first-move responses
static int try_opening_book()
{
    if (fullmove_number != 1) return 0;

    if (side == white) {
        // Randomly play e4 or d4
        srand(get_time_ms());
        int choice = rand() % 2;
        char *move_str = choice ? "e2e4" : "d2d4";
        int move = parse_move(move_str);
        if (move) {
            printf("bestmove %s\n", move_str);
            fflush(stdout);
            return 1;
        }
    } else {
        // Respond to e4 with e5, d4 with d5
        // Check if white pawn is on e4 (square e4 in BBC = rank 4, file 4 = sq 36)
        if (get_bit(bitboards[P], 36) && !get_bit(bitboards[P], 12)) {
            // e4 was played, respond with e5
            int move = parse_move("e7e5");
            if (move) {
                printf("bestmove e7e5\n");
                fflush(stdout);
                return 1;
            }
        }
        if (get_bit(bitboards[P], 35) && !get_bit(bitboards[P], 11)) {
            // d4 was played, respond with d5
            int move = parse_move("d7d5");
            if (move) {
                printf("bestmove d7d5\n");
                fflush(stdout);
                return 1;
            }
        }
    }
    return 0;
}

// Main UCI loop
void uci_loop()
{
    setbuf(stdin, NULL);
    setbuf(stdout, NULL);

    char input[2000];

    while (1) {
        memset(input, 0, sizeof(input));
        fflush(stdout);

        if (!fgets(input, 2000, stdin))
            continue;

        if (input[0] == '\n')
            continue;

        if (strncmp(input, "isready", 7) == 0) {
            printf("readyok\n");
            fflush(stdout);
            continue;
        }

        if (strncmp(input, "position", 8) == 0) {
            parse_position(input);
            continue;
        }

        if (strncmp(input, "ucinewgame", 10) == 0) {
            parse_position("position startpos");
            clear_hash_table();
            continue;
        }

        if (strncmp(input, "go", 2) == 0) {
            // Try opening book first
            if (!try_opening_book())
                parse_go(input);
            continue;
        }

        if (strncmp(input, "quit", 4) == 0)
            break;

        if (strncmp(input, "uci", 3) == 0) {
            printf("id name v13\n");
            printf("id author tomberkley\n");
            printf("uciok\n");
            fflush(stdout);
        }
    }
}


/**********************************\
 ==================================

           Init all + Main

 ==================================
\**********************************/

void init_all()
{
    init_leapers_attacks();
    init_sliders_attacks(bishop);
    init_sliders_attacks(rook);
    init_random_keys();
    init_evaluation_masks();
    init_lmr_table();
    clear_hash_table();
}

int main()
{
    init_all();
    uci_loop();
    return 0;
}

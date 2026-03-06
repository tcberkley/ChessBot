
// system headers
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <unistd.h>
#include <pthread.h>
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

// Lazy SMP: number of search threads
int num_threads = 1;
#define MAX_THREADS 8

// Master board state — copied to each worker thread at search start
static U64  master_bitboards[12];
static U64  master_occupancies[3];
static int  master_side, master_enpassant, master_castle;
static U64  master_hash_key;
static U64  master_repetition_table[1000];
static int  master_repetition_index;
static int  master_ply;
static int  master_has_castled[2];
static int  master_fullmove_number;
static int  master_halfmove_clock;

// piece bitboards
__thread U64 bitboards[12];

// occupancy bitboards
__thread U64 occupancies[3];


// side to move
__thread int side;

// enpassant square
__thread int enpassant;

// castling rights
__thread int castle;

// "almost" unique position identifier aka hash key or position key
__thread U64 hash_key;

// positions repetition table
__thread U64 repetition_table[1000];  // 1000 is a number of plies (500 moves) in the entire game

// repetition index
__thread int repetition_index;

// half move counter
__thread int ply;

// v12 additions: castling tracking and fullmove number
__thread int has_castled[2]; // has_castled[white], has_castled[black]
__thread int fullmove_number;

// v16: halfmove clock for 50-move rule
__thread int halfmove_clock;

// v18 SE: move excluded from the singular extension verification search (0 = none)
__thread int se_excluded_move;


/**********************************\
 ==================================
 
       Time controls variables
 
 ==================================
\**********************************/

// exit from engine flag
int quit = 0;

// v13 search stop flag (declared here so read_input can use it, defined in search section)
int v14_stopped = 0;

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
        // loop to read bytes from STDIN
        do
        {
            bytes=read(fileno(stdin), input, 256);
        }
        while (bytes < 0);

        // searches for the first occurrence of '\n'
        endc = strchr(input,'\n');
        if (endc) *endc=0;

        if (strlen(input) > 0)
        {
            if (!strncmp(input, "quit", 4))
            {
                quit = 1;
                stopped = 1;
                v14_stopped = 1;
            }
            else if (!strncmp(input, "stop", 4))
            {
                stopped = 1;
                v14_stopped = 1;
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

// count bits within a bitboard (hardware popcount)
static inline int count_bits(U64 bitboard)
{
    return __builtin_popcountll(bitboard);
}

// get least significant 1st bit index (hardware ctz)
static inline int get_ls1b_index(U64 bitboard)
{
    if (bitboard)
        return __builtin_ctzll(bitboard);
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
    halfmove_clock = 0;

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

    // v16: parse halfmove clock for 50-move rule
    if (*fen == ' ') {
        fen++;
        halfmove_clock = atoi(fen);
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
    int halfmove_clock_copy = halfmove_clock;                             \

// restore board state
#define take_back()                                                       \
    memcpy(bitboards, bitboards_copy, 96);                                \
    memcpy(occupancies, occupancies_copy, 24);                            \
    side = side_copy, enpassant = enpassant_copy, castle = castle_copy;   \
    hash_key = hash_key_copy;                                             \
    memcpy(has_castled, has_castled_copy, 8);                             \
    fullmove_number = fullmove_copy;                                      \
    halfmove_clock = halfmove_clock_copy;                                 \

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

        // v16: update halfmove clock for 50-move rule (reset on pawn move or capture)
        if (piece == P || piece == p || capture)
            halfmove_clock = 0;
        else
            halfmove_clock++;

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
__thread U64 nodes;

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
const int v14_piece_values[12] = {
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

// Knight PST (shared MG/EG — knights are piece-square-stable across phases)
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

// Bishop middlegame PST
const int pst_bishop_mg[64] = {
   -20,-10,-10,-10,-10,-10,-10,-20,
   -10,  5,  0,  0,  0,  0,  5,-10,
   -10, 10, 10, 10, 10, 10, 10,-10,
   -10,  0, 10, 10, 10, 10,  0,-10,
   -10,  5,  5, 10, 10,  5,  5,-10,
   -10,  0,  5, 10, 10,  5,  0,-10,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -20,-10,-10,-10,-10,-10,-10,-20,
};

// Bishop endgame PST — reward long diagonals and central activity
const int pst_bishop_eg[64] = {
   -20,-10,-10,-10,-10,-10,-10,-20,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -10,  0, 10, 10, 10, 10,  0,-10,
   -10,  0, 10, 20, 20, 10,  0,-10,
   -10,  0, 10, 20, 20, 10,  0,-10,
   -10,  0, 10, 10, 10, 10,  0,-10,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -20,-10,-10,-10,-10,-10,-10,-20,
};

// Rook middlegame PST
const int pst_rook_mg[64] = {
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     0,  0,  0,  5,  5,  0,  0,  0,
};

// Rook endgame PST — centralized files more valuable, active ranks
const int pst_rook_eg[64] = {
     5,  5,  5,  5,  5,  5,  5,  5,
     5, 10, 10, 10, 10, 10, 10,  5,
     0,  5,  5,  5,  5,  5,  5,  0,
     0,  5,  5,  5,  5,  5,  5,  0,
     0,  5,  5,  5,  5,  5,  5,  0,
     0,  5,  5,  5,  5,  5,  5,  0,
    -5,  0,  0,  0,  0,  0,  0, -5,
     0,  0,  0,  5,  5,  0,  0,  0,
};

// Queen middlegame PST
const int pst_queen_mg[64] = {
   -20,-10,-10, -5, -5,-10,-10,-20,
   -10,  0,  5,  0,  0,  0,  0,-10,
   -10,  5,  5,  5,  5,  5,  0,-10,
     0,  0,  5,  5,  5,  5,  0, -5,
    -5,  0,  5,  5,  5,  5,  0, -5,
   -10,  0,  5,  5,  5,  5,  0,-10,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -20,-10,-10, -5, -5,-10,-10,-20,
};

// Queen endgame PST — centralized, more active in endgame
const int pst_queen_eg[64] = {
   -20,-10,-10, -5, -5,-10,-10,-20,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -10,  0, 10, 10, 10, 10,  0,-10,
    -5,  0, 10, 15, 15, 10,  0, -5,
    -5,  0, 10, 15, 15, 10,  0, -5,
   -10,  0, 10, 10, 10, 10,  0,-10,
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

// Fast material-only evaluation for lazy pruning in quiescence
static inline int evaluate_lazy()
{
    int score = 0;
    score += 100 * (count_bits(bitboards[P]) - count_bits(bitboards[p]));
    score += 320 * (count_bits(bitboards[N]) - count_bits(bitboards[n]));
    score += 330 * (count_bits(bitboards[B]) - count_bits(bitboards[b]));
    score += 500 * (count_bits(bitboards[R]) - count_bits(bitboards[r]));
    score += 900 * (count_bits(bitboards[Q]) - count_bits(bitboards[q]));
    return (side == white) ? score : -score;
}

// Pawn hash table — caches pawn structure eval (passed, doubled, isolated, islands)
typedef struct {
    U64 key;
    int white_score;
    int black_score;
    U64 white_passed;
    U64 black_passed;
} pawn_hash_entry;

#define PAWN_HASH_SIZE 8192
#define PAWN_HASH_MASK (PAWN_HASH_SIZE - 1)
static pawn_hash_entry pawn_table[PAWN_HASH_SIZE];

// Compute pawn structure score for one side; sets *out_passed to passed pawn bitboard.
// Called from evaluate() to fill the pawn hash table on a miss.
static int pawn_eval_side(int color, int phase, U64 *out_passed)
{
    int score = 0;
    int pawn_files[8] = {0};
    int pawn_file_mask = 0;
    U64 passed_bb = 0ULL;

    int pawn_piece = (color == white) ? P : p;
    int enemy_pawn = (color == white) ? p : P;
    U64 own_pawns_bb   = bitboards[pawn_piece];
    U64 enemy_pawns_bb = bitboards[enemy_pawn];

    U64 bb = own_pawns_bb;
    while (bb) {
        int sq   = get_ls1b_index(bb);
        int wsq  = (color == white) ? sq : mirror_score[sq];
        int file = sq & 7;
        int rank = get_rank[sq];

        score += 100;
        score += (pst_pawn_mg[wsq] * phase + pst_pawn_eg[wsq] * (TOTAL_PHASE - phase)) / TOTAL_PHASE;

        pawn_files[file]++;
        pawn_file_mask |= (1 << file);

        U64 *pass_masks = (color == white) ? white_passed_masks : black_passed_masks;
        if ((pass_masks[sq] & enemy_pawns_bb) == 0) {
            int advancement     = (color == white) ? (7 - rank) : rank;
            int pass_bonus_mg   = 50 * advancement / 6;
            int pass_bonus_eg   = 100 * advancement / 6;
            score += (pass_bonus_mg * phase + pass_bonus_eg * (TOTAL_PHASE - phase)) / TOTAL_PHASE;
            passed_bb |= (1ULL << sq);
        }

        int stop_sq = (color == white) ? sq - 8 : sq + 8;
        if (stop_sq >= 0 && stop_sq < 64 &&
            (pawn_attacks[color][stop_sq] & enemy_pawns_bb)) {
            U64 adj = ((file > 0) ? file_masks[file - 1] : 0ULL) |
                      ((file < 7) ? file_masks[file + 1] : 0ULL);
            U64 support = adj & own_pawns_bb;
            int supported = 0;
            while (support && !supported) {
                int sp = get_ls1b_index(support);
                int sr = get_rank[sp];
                if ((color == white && sr <= rank) || (color == black && sr >= rank))
                    supported = 1;
                pop_bit(support, sp);
            }
            if (!supported) score -= 10;
        }

        pop_bit(bb, sq);
    }

    for (int f = 0; f < 8; f++)
        if (pawn_files[f] >= 2) score -= 30 * (pawn_files[f] - 1);

    for (int f = 0; f < 8; f++) {
        if (pawn_files[f] > 0) {
            int has_neighbor = 0;
            if (f > 0 && (pawn_file_mask & (1 << (f - 1)))) has_neighbor = 1;
            if (f < 7 && (pawn_file_mask & (1 << (f + 1)))) has_neighbor = 1;
            if (!has_neighbor) score -= 20 * pawn_files[f];
        }
    }

    {
        int islands = 0, in_island = 0;
        for (int f = 0; f < 8; f++) {
            if (pawn_files[f] > 0 && !in_island) { islands++; in_island = 1; }
            else if (pawn_files[f] == 0) in_island = 0;
        }
        if (islands > 1) score -= (islands - 1) * 8;
    }

    *out_passed = passed_bb;
    return score;
}

// Evaluate one side's material + positional score
static inline int evaluate_side(int color, int phase, int pawn_score_in, U64 own_passed_bb_in)
{
    int score = pawn_score_in;
    int end_game = (phase < PHASE_THRESHOLD);
    int bishop_count = 0;

    // Piece indices for this side
    int pawn_piece   = (color == white) ? P : p;
    int knight_piece = (color == white) ? N : n;
    int bishop_piece = (color == white) ? B : b;
    int rook_piece   = (color == white) ? R : r;
    int queen_piece  = (color == white) ? Q : q;
    int king_piece   = (color == white) ? K : k;
    int enemy_pawn   = (color == white) ? p : P;
    int enemy_color  = 1 - color;

    U64 bb, occ_all = occupancies[both];
    U64 own_pawns_bb    = bitboards[pawn_piece];
    U64 enemy_pawns_bb  = bitboards[enemy_pawn];

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

        // Outpost: in opponent's half, not attackable by enemy pawns
        int rank = get_rank[sq];
        int in_opp_half = (color == white) ? (rank >= 4) : (rank <= 3);
        if (in_opp_half && !(pawn_attacks[color][sq] & enemy_pawns_bb)) {
            score += 15;
            // Extra bonus if defended by own pawn
            if (pawn_attacks[enemy_color][sq] & own_pawns_bb)
                score += 10;
        }

        pop_bit(bb, sq);
    }

    // === BISHOPS ===
    bb = bitboards[bishop_piece];
    while (bb) {
        int sq = get_ls1b_index(bb);
        int wsq = (color == white) ? sq : mirror_score[sq];
        score += 300;
        // Tapered bishop PST
        score += (pst_bishop_mg[wsq] * phase + pst_bishop_eg[wsq] * (TOTAL_PHASE - phase)) / TOTAL_PHASE;
        bishop_count++;
        // Mobility
        int mob = count_bits(get_bishop_attacks(sq, occ_all) & ~occupancies[color]);
        if (mob < 32) score += isqrt_x20[mob];
        // Bad bishop: penalize own pawns on the same color squares as this bishop
        {
            // Bishop square color: light if (file+rank) is even, dark if odd
            int bsq_color = (sq + (sq >> 3)) & 1;  // 0=light, 1=dark
            U64 pawns_bb = own_pawns_bb;
            int same_color_pawns = 0;
            while (pawns_bb) {
                int psq = get_ls1b_index(pawns_bb);
                if (((psq + (psq >> 3)) & 1) == bsq_color) same_color_pawns++;
                pop_bit(pawns_bb, psq);
            }
            score -= 5 * same_color_pawns;
        }
        pop_bit(bb, sq);
    }

    // === ROOKS ===
    U64 rooks_full_bb = bitboards[rook_piece];  // v16: save for connected rooks check
    bb = rooks_full_bb;
    while (bb) {
        int sq = get_ls1b_index(bb);
        int wsq = (color == white) ? sq : mirror_score[sq];
        int file = sq & 7;
        int rook_rank = get_rank[sq];
        score += 500;
        // Tapered rook PST
        score += (pst_rook_mg[wsq] * phase + pst_rook_eg[wsq] * (TOTAL_PHASE - phase)) / TOTAL_PHASE;
        // Mobility
        int mob = count_bits(get_rook_attacks(sq, occ_all) & ~occupancies[color]);
        if (mob < 32) score += isqrt_x20[mob];

        // Open / semi-open file bonus
        U64 rook_file_bb = file_masks[file];
        if (!(own_pawns_bb & rook_file_bb)) {
            score += (enemy_pawns_bb & rook_file_bb) ? 10 : 20;
        }

        // Rook on 7th rank (opponent's back rank territory)
        int seventh = (color == white) ? 6 : 1;  // BBC rank: 6=rank7, 1=rank2
        if (rook_rank == seventh)
            score += end_game ? 25 : 15;

        // v16: Rook behind own passed pawn bonus
        if (own_passed_bb_in) {
            U64 file_passers = own_passed_bb_in & file_masks[file];
            while (file_passers) {
                int psq = get_ls1b_index(file_passers);
                int p_rank = get_rank[psq];
                // get_rank returns chess rank 0-7 (0=rank1, 7=rank8).
                // White rook "behind" = lower chess rank than pawn (rook closer to rank 1).
                // Black rook "behind" = higher chess rank than pawn (rook closer to rank 8).
                if ((color == white && rook_rank < p_rank) ||
                    (color == black && rook_rank > p_rank)) {
                    score += 20;
                    break;
                }
                pop_bit(file_passers, psq);
            }
        }

        pop_bit(bb, sq);
    }

    // v16: Connected rooks bonus (rooks on same file/rank with clear path between them)
    if (count_bits(rooks_full_bb) >= 2) {
        int r1 = get_ls1b_index(rooks_full_bb);
        U64 tmp_r = rooks_full_bb;
        pop_bit(tmp_r, r1);
        int r2 = get_ls1b_index(tmp_r);
        int f1 = r1 & 7, rank1 = r1 >> 3;
        int f2 = r2 & 7, rank2 = r2 >> 3;
        if (f1 == f2) {
            // Same file — check for clear path
            int lo = rank1 < rank2 ? rank1 : rank2;
            int hi = rank1 < rank2 ? rank2 : rank1;
            int clear = 1;
            for (int r = lo + 1; r < hi; r++) {
                if (get_bit(occ_all, r * 8 + f1)) { clear = 0; break; }
            }
            if (clear) score += 15;
        } else if (rank1 == rank2) {
            // Same rank — check for clear path
            int lo_f = f1 < f2 ? f1 : f2;
            int hi_f = f1 < f2 ? f2 : f1;
            int clear = 1;
            for (int f = lo_f + 1; f < hi_f; f++) {
                if (get_bit(occ_all, rank1 * 8 + f)) { clear = 0; break; }
            }
            if (clear) score += 15;
        }
    }

    // === QUEENS ===
    bb = bitboards[queen_piece];
    while (bb) {
        int sq = get_ls1b_index(bb);
        int wsq = (color == white) ? sq : mirror_score[sq];
        score += 900;
        // Tapered queen PST
        score += (pst_queen_mg[wsq] * phase + pst_queen_eg[wsq] * (TOTAL_PHASE - phase)) / TOTAL_PHASE;
        // Mobility
        int mob = count_bits(get_queen_attacks(sq, occ_all) & ~occupancies[color]);
        if (mob < 32) score += isqrt_x20[mob];
        pop_bit(bb, sq);
    }

    // === KING ===
    {
        int sq = get_ls1b_index(bitboards[king_piece]);
        int wsq = (color == white) ? sq : mirror_score[sq];
        int king_file = sq & 7;

        // Tapered king PST
        score += (pst_king_mg[wsq] * phase + pst_king_eg[wsq] * (TOTAL_PHASE - phase)) / TOTAL_PHASE;

        // King safety (middlegame only)
        if (!end_game) {
            // v16: Pawn shield quality (penalize advanced shield pawns)
            // get_rank[sq] = chess rank index: 0=rank1, 7=rank8.
            // White king is on a low rank; a shield pawn is 1-2 ranks higher.
            // Black king is on a high rank; a shield pawn is 1-2 ranks lower.
            int king_rank = get_rank[sq];
            for (int kf = king_file - 1; kf <= king_file + 1; kf++) {
                if (kf < 0 || kf > 7) continue;
                U64 pawns_on_file = own_pawns_bb & file_masks[kf];
                int has_immediate = 0, has_advanced = 0;
                while (pawns_on_file) {
                    int psq = get_ls1b_index(pawns_on_file);
                    int p_rank = get_rank[psq];
                    int rank_dist;
                    if (color == white)
                        rank_dist = p_rank - king_rank;  // positive = pawn ahead of king
                    else
                        rank_dist = king_rank - p_rank;  // positive = pawn ahead of king
                    if (rank_dist == 1) has_immediate = 1;
                    else if (rank_dist == 2) has_advanced = 1;
                    pop_bit(pawns_on_file, psq);
                }
                if (has_immediate) score += 15;
                else if (has_advanced) score += 8;
                // missing pawn: no extra penalty here (open file penalty handles it)
            }

            // Open / semi-open file penalty near king (half-weight: -10 open, -5 semi-open)
            for (int kf = king_file - 1; kf <= king_file + 1; kf++) {
                if (kf < 0 || kf > 7) continue;
                U64 kfile_bb = file_masks[kf];
                if (!(own_pawns_bb & kfile_bb))
                    score -= (enemy_pawns_bb & kfile_bb) ? 5 : 10;
            }

            // v17: King attack count scoring
            {
                U64 king_zone = king_attacks[sq];
                int king_danger = 0;
                int enemy_knight = (color == white) ? n : N;
                int enemy_bishop = (color == white) ? b : B;
                int enemy_rook   = (color == white) ? r : R;
                int enemy_queen  = (color == white) ? q : Q;

                // Enemy pawns (weight 1)
                U64 ep_bb = bitboards[enemy_pawn];
                while (ep_bb) {
                    int esq = get_ls1b_index(ep_bb);
                    if (pawn_attacks[enemy_color][esq] & king_zone) king_danger += 1;
                    pop_bit(ep_bb, esq);
                }
                // Enemy knights (weight 2)
                U64 en_bb = bitboards[enemy_knight];
                while (en_bb) {
                    int esq = get_ls1b_index(en_bb);
                    if (knight_attacks[esq] & king_zone) king_danger += 2;
                    pop_bit(en_bb, esq);
                }
                // Enemy bishops (weight 2)
                U64 eb_bb = bitboards[enemy_bishop];
                while (eb_bb) {
                    int esq = get_ls1b_index(eb_bb);
                    if (get_bishop_attacks(esq, occ_all) & king_zone) king_danger += 2;
                    pop_bit(eb_bb, esq);
                }
                // Enemy rooks (weight 3)
                U64 er_bb = bitboards[enemy_rook];
                while (er_bb) {
                    int esq = get_ls1b_index(er_bb);
                    if (get_rook_attacks(esq, occ_all) & king_zone) king_danger += 3;
                    pop_bit(er_bb, esq);
                }
                // Enemy queen (weight 5)
                U64 eq_bb = bitboards[enemy_queen];
                while (eq_bb) {
                    int esq = get_ls1b_index(eq_bb);
                    U64 q_attacks = get_bishop_attacks(esq, occ_all) | get_rook_attacks(esq, occ_all);
                    if (q_attacks & king_zone) king_danger += 5;
                    pop_bit(eq_bb, esq);
                }

                // Non-linear danger penalty (quadratic, capped at 150 cp)
                if (king_danger > 0) {
                    int penalty = king_danger * king_danger / 4;
                    if (penalty > 150) penalty = 150;
                    score -= penalty;
                }
            }
        }

        // King endgame bonuses
        if (end_game) {
            int rank = sq >> 3;  // BBC rank 0-7
            int file = sq & 7;
            // Centralization
            int rank_dist = rank > 3 ? rank - 3 : 4 - rank;
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

            // v16: King mobility bonus in endgame — king is an active piece
            U64 king_safe_moves = king_attacks[sq] & ~occupancies[color];
            score += count_bits(king_safe_moves) * 3;
        }
    }

    // === Bishop pair bonus ===
    if (bishop_count >= 2)
        score += 30;

    // === Castling bonuses ===
    if (color == white) {
        if (castle & wk) score += 10;
        if (castle & wq) score += 10;
    } else {
        if (castle & bk) score += 10;
        if (castle & bq) score += 10;
    }
    if (has_castled[color])
        score += 40;

    return score;
}

// Main evaluation function (returns score from side-to-move perspective)
static inline int evaluate()
{
    // v16: Insufficient material detection
    int total_pieces = count_bits(occupancies[both]);
    if (total_pieces == 2) return 0;  // KK
    if (total_pieces == 3) {
        if (count_bits(bitboards[N]) + count_bits(bitboards[n]) +
            count_bits(bitboards[B]) + count_bits(bitboards[b]) == 1)
            return 0;
    }

    int phase = get_game_phase();

    // v18: Pawn hash — cache pawn structure eval for both sides.
    // Phase is included in the key because pawn_eval_side() bakes tapered PST
    // scores into the cached result; a stale entry at a different phase would
    // return a score computed with the wrong MG/EG blend.
    U64 pkey = bitboards[P] * 0x9e3779b97f4a7c15ULL ^
               bitboards[p] * 0x517cc1b727220a95ULL ^
               (U64)phase;
    int pidx = (int)(pkey & PAWN_HASH_MASK);
    pawn_hash_entry *phe = &pawn_table[pidx];
    U64 white_passed = 0ULL, black_passed = 0ULL;
    int wpawn_score, bpawn_score;

    if (phe->key == pkey) {
        // Cache hit
        wpawn_score  = phe->white_score;
        bpawn_score  = phe->black_score;
        white_passed = phe->white_passed;
        black_passed = phe->black_passed;
    } else {
        // Cache miss: compute for both sides and store
        wpawn_score = pawn_eval_side(white, phase, &white_passed);
        bpawn_score = pawn_eval_side(black, phase, &black_passed);
        phe->key          = pkey;
        phe->white_score  = wpawn_score;
        phe->black_score  = bpawn_score;
        phe->white_passed = white_passed;
        phe->black_passed = black_passed;
    }

    int white_score = evaluate_side(white, phase, wpawn_score, white_passed);
    int black_score = evaluate_side(black, phase, bpawn_score, black_passed);
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

// v17: Clustered TT — 4 entries per 64-byte cache line.
// Same total memory (4M entries × 16 bytes = 64MB) but dramatically higher hit rate:
// probing all 4 entries in a cluster costs zero extra cache misses since the whole
// cluster is fetched in one shot.
#define TT_CLUSTER_SIZE 4
#define TT_NUM_CLUSTERS (1 << 20)       // 1M clusters = 4M entries = 64MB
#define TT_CLUSTER_MASK (TT_NUM_CLUSTERS - 1)
// Keep TT_MASK alias so prefetch call compiles unchanged
#define TT_MASK TT_CLUSTER_MASK

#define NO_HASH_ENTRY 100000

#define HASH_FLAG_EXACT 0
#define HASH_FLAG_ALPHA 1  // UPPERBOUND
#define HASH_FLAG_BETA  2  // LOWERBOUND

typedef struct {
    unsigned int hash32;   // upper 32 bits of Zobrist key
    int best_move;         // 4 bytes
    int score;             // 4 bytes
    signed char depth;     // 1 byte
    unsigned char flag;    // 1 byte
    unsigned char pad[2];  // 2 bytes padding
} tt_entry;                // 16 bytes

typedef struct {
    tt_entry entries[TT_CLUSTER_SIZE];  // 64 bytes = exactly one cache line
} tt_cluster;

// Aligned to 64 bytes so each cluster starts on a cache line boundary
tt_cluster hash_table[TT_NUM_CLUSTERS] __attribute__((aligned(64)));

void clear_hash_table()
{
    memset(hash_table, 0, sizeof(hash_table));
}

// Read TT entry; returns NO_HASH_ENTRY if not found.
// Searches all 4 entries in the cluster — all fit in one cache line so no extra misses.
// Also extracts best_move from any matching entry for move ordering (regardless of depth).
static inline int read_hash_entry(int alpha, int beta, int depth, int *tt_best_move)
{
    tt_cluster *cluster = &hash_table[hash_key & TT_CLUSTER_MASK];
    unsigned int hash32 = (unsigned int)(hash_key >> 32);

    for (int i = 0; i < TT_CLUSTER_SIZE; i++) {
        tt_entry *entry = &cluster->entries[i];
        if (entry->hash32 == hash32) {
            // Always extract best move for move ordering
            *tt_best_move = entry->best_move;

            if ((int)entry->depth >= depth) {
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
            return NO_HASH_ENTRY;  // Key matched but depth/bound didn't — stop searching
        }
    }

    return NO_HASH_ENTRY;
}

// Peek at TT entry for singular extension: returns 1 on hit, populates score/flag/depth.
// Unlike read_hash_entry, no alpha/beta logic — we want raw stored values.
static inline int get_tt_info(int *out_score, int *out_flag, int *out_depth)
{
    tt_cluster *cluster = &hash_table[hash_key & TT_CLUSTER_MASK];
    unsigned int hash32 = (unsigned int)(hash_key >> 32);
    for (int i = 0; i < TT_CLUSTER_SIZE; i++) {
        tt_entry *e = &cluster->entries[i];
        if (e->hash32 == hash32) {
            int s = e->score;
            if (s < -mate_score) s += ply;
            if (s > mate_score) s -= ply;
            *out_score = s;
            *out_flag  = (int)e->flag;
            *out_depth = (int)(signed char)e->depth;
            return 1;
        }
    }
    return 0;
}

// Write TT entry.
// Replacement policy: prefer to reuse a matching slot (same position);
// otherwise replace the slot with the lowest depth (least valuable entry).
static inline void write_hash_entry(int score, int depth, int flag, int best_move)
{
    tt_cluster *cluster = &hash_table[hash_key & TT_CLUSTER_MASK];
    unsigned int hash32 = (unsigned int)(hash_key >> 32);

    // Adjust mate scores for storage
    if (score < -mate_score) score -= ply;
    if (score > mate_score) score += ply;

    // Find: matching entry to update, OR lowest-depth entry to replace
    tt_entry *replace = &cluster->entries[0];
    for (int i = 0; i < TT_CLUSTER_SIZE; i++) {
        tt_entry *entry = &cluster->entries[i];
        if (entry->hash32 == hash32) {
            // Found this position's slot. Update if new depth >= stored, or always for exact.
            if (depth >= (int)entry->depth || flag == HASH_FLAG_EXACT) {
                replace = entry;
            } else {
                // Shallower non-exact result: just refresh the best_move if we have one
                if (best_move) entry->best_move = best_move;
                return;
            }
            break;
        }
        // Track replacement candidate: empty slot or lowest depth
        if (entry->hash32 == 0 || (int)entry->depth < (int)replace->depth)
            replace = entry;
    }

    replace->hash32    = hash32;
    replace->depth     = (signed char)depth;
    replace->score     = score;
    replace->flag      = (unsigned char)flag;
    replace->best_move = best_move;
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

// Countermove heuristic [piece][to_square] — best response to opponent's last move
int countermove[12][64];

// Previous move tracking for countermove (piece that moved and its destination)
__thread int prev_move_piece;
__thread int prev_move_to;

// Capture history [attacker_piece][to_sq][captured_piece]
int capture_history[12][64][12];

// 1-ply continuation history [prev_piece][prev_to][cur_piece][cur_to]
short cont_hist[12][64][12][64];

// PV table
__thread int pv_length[max_ply];
__thread int pv_table[max_ply][max_ply];

// Pre-computed LMR reduction table
int lmr_table[64][64];

// Futility margins indexed by depth (centipawns)
const int futility_margins[3] = {0, 150, 350};

// Time control globals
int v14_time_budget_ms = 0;    // allocated time for this move in ms
long v14_search_start = 0;     // start time in ms
// v14_stopped declared near top of file with other globals
int v14_hard_limit_ms = 0;     // absolute max time (safety net: don't use >50% of clock)
#define TIME_CHECK_INTERVAL 4096

// Initialize LMR table
void init_lmr_table()
{
    for (int d = 1; d < 64; d++)
        for (int m = 1; m < 64; m++)
            lmr_table[d][m] = (int)(1.0 + log(d) * log(m) / 2.5);
}

// Check if we should stop searching (time + GUI input)
static inline void check_time()
{
    if (v14_time_budget_ms > 0) {
        long elapsed = get_time_ms() - v14_search_start;
        // Normal budget: stop at 90%
        if (elapsed > (long)(v14_time_budget_ms * 0.9))
            v14_stopped = 1;
        // Hard safety limit: never exceed this (prevents losing on time)
        if (v14_hard_limit_ms > 0 && elapsed > v14_hard_limit_ms)
            v14_stopped = 1;
    }
    // NOTE: Do NOT call read_input() here. raw read() can consume
    // multiple lines from stdin, eating position/go commands meant
    // for the UCI loop. Time management alone stops the search.
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

// SEE piece values (centipawns)
static const int see_piece_val[12] = {100, 300, 300, 500, 900, 20000, 100, 300, 300, 500, 900, 20000};

// Returns bitboard of all pieces attacking square sq with the given occupancy
static inline U64 get_attackers_to(int sq, U64 occ)
{
    return (pawn_attacks[black][sq] & bitboards[P]) |
           (pawn_attacks[white][sq] & bitboards[p]) |
           (knight_attacks[sq]      & (bitboards[N] | bitboards[n])) |
           (get_bishop_attacks(sq, occ) & (bitboards[B] | bitboards[b] | bitboards[Q] | bitboards[q])) |
           (get_rook_attacks(sq, occ)   & (bitboards[R] | bitboards[r] | bitboards[Q] | bitboards[q])) |
           (king_attacks[sq]        & (bitboards[K] | bitboards[k]));
}

// Static Exchange Evaluation: returns estimated net material gain for a capture.
// Positive = winning/equal capture, negative = losing.
// attacker_piece: piece enum (0-11) of the initial capturer
// target_val: value in cp of the piece being captured
static int see(int from_sq, int to_sq, int attacker_piece, int target_val)
{
    int gain[32], d = 0;
    U64 occ = occupancies[both];
    U64 attadef = get_attackers_to(to_sq, occ);

    gain[d] = target_val;

    int stm = (attacker_piece < 6) ? white : black;
    U64 from_bb = 1ULL << from_sq;
    int next_piece = attacker_piece;

    do {
        d++;
        gain[d] = see_piece_val[next_piece] - gain[d - 1];

        // Remove this attacker and reveal x-ray pieces
        occ     ^= from_bb;
        attadef ^= from_bb;
        attadef |= get_bishop_attacks(to_sq, occ) & (bitboards[B] | bitboards[b] | bitboards[Q] | bitboards[q]);
        attadef |= get_rook_attacks(to_sq, occ)   & (bitboards[R] | bitboards[r] | bitboards[Q] | bitboards[q]);
        attadef &= occ;

        stm ^= 1;

        // Find least valuable attacker for the new side
        next_piece = -1;
        from_bb = 0ULL;
        int start = stm * 6;
        for (int pc = start; pc < start + 6; pc++) {
            U64 s = attadef & bitboards[pc];
            if (s) {
                next_piece = pc;
                from_bb = s & (-s);  // isolate LSB
                break;
            }
        }
    } while (next_piece >= 0 && d < 31);

    // Propagate backwards: each side stops if recapturing isn't profitable
    while (--d)
        gain[d - 1] = (gain[d - 1] < -gain[d]) ? gain[d - 1] : -gain[d];

    return gain[0];
}

// Score a move for ordering
// Priority: TT move (2M) > winning captures MVV-LVA (1M+) > killer (900k/800k) > countermove (700k) > losing captures (500k+) > history
static inline int score_move(int move, int tt_move)
{
    // TT move gets highest priority
    if (move == tt_move)
        return 2000000;

    // Captures: use SEE to split winning (>=0) and losing (<0) captures
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
        int see_val = see(get_move_source(move), get_move_target(move),
                          get_move_piece(move), see_piece_val[target_piece]);
        // Add capture_history as tiebreaker within SEE groups (capped to ±400)
        int ch_bonus = capture_history[get_move_piece(move)][get_move_target(move)][target_piece];
        if (ch_bonus >  400) ch_bonus =  400;
        if (ch_bonus < -400) ch_bonus = -400;
        if (see_val >= 0)
            return mvv_lva[get_move_piece(move)][target_piece] + 1000000 + ch_bonus;
        else
            return mvv_lva[get_move_piece(move)][target_piece] + 500000  + ch_bonus;
    }

    // Killer moves
    if (killer_moves[0][ply] == move) return 900000;
    if (killer_moves[1][ply] == move) return 800000;

    // Countermove heuristic: response to opponent's last move
    if (prev_move_piece && countermove[prev_move_piece][prev_move_to] == move)
        return 700000;

    // History heuristic + 1-ply continuation history
    {
        int hist = history_moves[get_move_piece(move)][get_move_target(move)];
        if (prev_move_piece) {
            int cont = cont_hist[prev_move_piece][prev_move_to][get_move_piece(move)][get_move_target(move)];
            hist += cont;
        }
        return hist;
    }
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
    nodes++;

    // Time check
    if ((nodes & (TIME_CHECK_INTERVAL - 1)) == 0)
        check_time();

    if (v14_stopped) return 0;

    if (ply > max_ply - 1)
        return evaluate();

    // v18: Lazy eval guard — skip full evaluate() if material is clearly outside window
    {
        int lazy = evaluate_lazy();
        if (lazy + 350 < alpha) return alpha;
        if (lazy - 350 > beta)  return beta;
    }

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
        int move = move_list->moves[count];

        // Skip non-captures (captures sorted first, so break when we hit a quiet)
        if (!get_move_capture(move)) break;

        // SEE filter: skip captures that lose material (e.g. QxP defended by pawn)
        {
            int tp = P;
            int sp = (side == white) ? p : P;
            int ep = (side == white) ? k : K;
            for (int bb_pc = sp; bb_pc <= ep; bb_pc++) {
                if (get_bit(bitboards[bb_pc], get_move_target(move))) { tp = bb_pc; break; }
            }
            if (see(get_move_source(move), get_move_target(move),
                    get_move_piece(move), see_piece_val[tp]) < 0)
                continue;
        }

        copy_board();
        ply++;
        repetition_index++;
        repetition_table[repetition_index] = hash_key;

        if (make_move(move, all_moves) == 0) {
            ply--;
            repetition_index--;
            continue;
        }

        int score = -quiescence(-beta, -alpha);

        ply--;
        repetition_index--;
        take_back();

        if (v14_stopped) return 0;

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
    nodes++;

    // Time check
    if ((nodes & (TIME_CHECK_INTERVAL - 1)) == 0)
        check_time();

    if (v14_stopped) return 0;

    // Init PV length
    pv_length[ply] = ply;

    // Repetition detection
    if (ply && is_repetition())
        return 0;

    // v16: 50-move rule draw detection
    if (ply && halfmove_clock >= 100)
        return 0;

    // PV node flag
    int pv_node = (beta - alpha > 1);

    // TT lookup (prefetch full 64-byte cluster into cache before other work)
    __builtin_prefetch(&hash_table[hash_key & TT_CLUSTER_MASK], 0, 1);
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

        int R = 3 + depth / 6; if (R >= depth) R = depth - 1;
        int null_score = -negamax(-beta, -beta + 1, depth - 1 - R, 0);

        ply--;
        repetition_index--;
        take_back();

        if (v14_stopped) return 0;

        if (null_score >= beta)
            return beta;
    }

    // v18: Probcut — at non-PV nodes depth>=5, prune captures that beat a wide threshold
    if (!pv_node && depth >= 5 && !in_check &&
        beta > -mate_score && beta < mate_score) {
        int pc_beta = beta + 200;
        int saved_cm_p = prev_move_piece, saved_cm_t = prev_move_to;
        moves pc_list[1];
        generate_moves(pc_list);
        for (int pi = 0; pi < pc_list->count; pi++) {
            int pc_move = pc_list->moves[pi];
            if (!get_move_capture(pc_move)) continue;

            // Quick SEE filter
            int tp = P;
            { int sp2 = (side == white) ? p : P, ep2 = (side == white) ? k : K;
              for (int bpc = sp2; bpc <= ep2; bpc++)
                  if (get_bit(bitboards[bpc], get_move_target(pc_move))) { tp = bpc; break; } }
            if (see(get_move_source(pc_move), get_move_target(pc_move),
                    get_move_piece(pc_move), see_piece_val[tp]) < pc_beta - beta - 1)
                continue;

            copy_board();
            ply++;
            repetition_index++;
            repetition_table[repetition_index] = hash_key;
            prev_move_piece = get_move_piece(pc_move);
            prev_move_to    = get_move_target(pc_move);

            if (make_move(pc_move, all_moves) == 0) {
                ply--; repetition_index--; continue;
            }

            int pc_score = -negamax(-pc_beta, -pc_beta + 1, depth - 4, 0);

            ply--;
            repetition_index--;
            take_back();

            if (v14_stopped) return 0;
            if (pc_score >= pc_beta) {
                prev_move_piece = saved_cm_p;
                prev_move_to    = saved_cm_t;
                return pc_beta;
            }
        }
        prev_move_piece = saved_cm_p;
        prev_move_to    = saved_cm_t;
    }

    // Futility pruning setup (compute eval once for both forward and reverse)
    int futile = 0;
    if (depth <= 3 && !in_check && !pv_node) {
        // Tempo bonus: side to move has a slight initiative advantage (+10 cp)
        int static_eval = evaluate() + 10;

        // Reverse futility pruning: if eval - margin >= beta, this node is too good
        // for opponent to allow, so prune it
        if (static_eval - 100 * depth >= beta && beta > -mate_score && beta < mate_score)
            return static_eval;

        // Forward futility pruning: if eval + margin <= alpha, quiet moves won't help
        if (depth <= 2 && alpha > -mate_score && alpha < mate_score) {
            if (static_eval + futility_margins[depth] <= alpha)
                futile = 1;
        }
    }

    // v16: IID — if PV node with no TT move and deep enough, do shallow search for move ordering
    if (pv_node && tt_best_move == 0 && depth >= 5) {
        negamax(alpha, beta, depth - 2, 0);
        read_hash_entry(alpha, beta, depth, &tt_best_move);
    }

    // Save opponent's last move for countermove heuristic lookup/storage
    int cm_piece = prev_move_piece;
    int cm_to = prev_move_to;

    // v18: Singular extension — if the TT move is the only good move at this node, extend it.
    // Conditions: non-PV, depth>=8, have a TT move, not in check, not at root,
    // not already inside an SE search (se_excluded_move!=0), TT entry is reliable.
    int se_extension = 0;
    if (!pv_node && depth >= 8 && tt_best_move && !in_check && ply > 0
        && !se_excluded_move) {
        int se_tt_score, se_tt_flag, se_tt_depth;
        if (get_tt_info(&se_tt_score, &se_tt_flag, &se_tt_depth)
            && se_tt_depth >= depth - 3
            && (se_tt_flag == HASH_FLAG_EXACT || se_tt_flag == HASH_FLAG_BETA)
            && se_tt_score > -mate_score && se_tt_score < mate_score) {
            int se_beta = se_tt_score - 25 * depth;
            se_excluded_move = tt_best_move;
            int se_score = negamax(se_beta - 1, se_beta, depth / 2, 0);
            se_excluded_move = 0;
            if (!v14_stopped && se_score < se_beta)
                se_extension = 1;
        }
    }

    int legal_moves_count = 0;
    int best_score = -infinity;
    int best_move = 0;
    int hash_flag = HASH_FLAG_ALPHA;

    // v18: Try TT move first before generating all moves (saves generate_moves on TT cutoffs)
    // Skip if this move is excluded (we are inside the SE verification search for it).
    if (tt_best_move && tt_best_move != se_excluded_move) {
        copy_board();
        ply++;
        repetition_index++;
        repetition_table[repetition_index] = hash_key;
        prev_move_piece = get_move_piece(tt_best_move);
        prev_move_to    = get_move_target(tt_best_move);

        if (make_move(tt_best_move, all_moves)) {
            legal_moves_count = 1;
            int futile_tt = futile && legal_moves_count > 0 &&
                            !get_move_capture(tt_best_move) && !get_move_promoted(tt_best_move);
            int tt_score;
            if (!futile_tt) {
                tt_score = -negamax(-beta, -alpha, depth - 1 + se_extension, 1);
            } else {
                tt_score = alpha;  // skip futile TT quiet moves too
            }

            ply--;
            repetition_index--;
            take_back();

            if (v14_stopped) { prev_move_piece = cm_piece; prev_move_to = cm_to; return 0; }

            if (tt_score > best_score) {
                best_score = tt_score;
                best_move  = tt_best_move;
            }
            if (tt_score > alpha) {
                hash_flag = HASH_FLAG_EXACT;
                alpha = tt_score;
                int is_tt_cap = get_move_capture(tt_best_move);
                if (!is_tt_cap) {
                    int bonus = depth * depth;
                    history_moves[get_move_piece(tt_best_move)][get_move_target(tt_best_move)] +=
                        bonus - history_moves[get_move_piece(tt_best_move)][get_move_target(tt_best_move)] * bonus / 16384;
                }
                pv_table[ply][ply] = tt_best_move;
                for (int np = ply + 1; np < pv_length[ply + 1]; np++)
                    pv_table[ply][np] = pv_table[ply + 1][np];
                pv_length[ply] = pv_length[ply + 1];

                if (tt_score >= beta) {
                    write_hash_entry(beta, depth, HASH_FLAG_BETA, tt_best_move);
                    if (!is_tt_cap) {
                        killer_moves[1][ply] = killer_moves[0][ply];
                        killer_moves[0][ply] = tt_best_move;
                        if (cm_piece) countermove[cm_piece][cm_to] = tt_best_move;
                        if (cm_piece) {
                            int cb = depth * depth;
                            short *ch = &cont_hist[cm_piece][cm_to][get_move_piece(tt_best_move)][get_move_target(tt_best_move)];
                            int cv = (int)*ch + cb - (int)*ch * cb / 16384;
                            *ch = (short)(cv > 32767 ? 32767 : (cv < -32768 ? -32768 : cv));
                        }
                    }
                    prev_move_piece = cm_piece;
                    prev_move_to    = cm_to;
                    return beta;
                }
            }
        } else {
            ply--;
            repetition_index--;
        }
        prev_move_piece = cm_piece;
        prev_move_to    = cm_to;
    }

    // Generate and sort remaining moves
    moves move_list[1];
    generate_moves(move_list);
    sort_moves(move_list, tt_best_move);

    for (int count = 0; count < move_list->count; count++) {
        int move = move_list->moves[count];
        if (move == tt_best_move) continue;       // already tried in pre-try stage
        if (move == se_excluded_move) continue;   // excluded from SE verification search
        int is_capture = get_move_capture(move);
        int is_promotion = get_move_promoted(move);

        // v18: Find captured piece for capture_history (must be before copy_board)
        int captured_piece_idx = -1;
        if (is_capture) {
            int sp2 = (side == white) ? p : P;
            int ep2 = (side == white) ? k : K;
            for (int bpc = sp2; bpc <= ep2; bpc++) {
                if (get_bit(bitboards[bpc], get_move_target(move))) {
                    captured_piece_idx = bpc; break;
                }
            }
        }

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

        // Tell recursive call what our move was (for countermove lookup at depth-1)
        prev_move_piece = get_move_piece(move);
        prev_move_to = get_move_target(move);

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
            if (!v14_stopped && score > alpha && (reduction > 0 || score < beta))
                score = -negamax(-beta, -alpha, depth - 1, 1);
        }

        ply--;
        repetition_index--;
        take_back();

        if (v14_stopped) return 0;

        if (score > best_score) {
            best_score = score;
            best_move = move;

            if (score > alpha) {
                hash_flag = HASH_FLAG_EXACT;
                alpha = score;

                // Store history for quiet moves (with gravity scaling)
                if (!is_capture) {
                    int bonus = depth * depth;
                    history_moves[get_move_piece(move)][get_move_target(move)] +=
                        bonus - history_moves[get_move_piece(move)][get_move_target(move)] * bonus / 16384;
                }

                // Write PV
                pv_table[ply][ply] = move;
                for (int next_ply = ply + 1; next_ply < pv_length[ply + 1]; next_ply++)
                    pv_table[ply][next_ply] = pv_table[ply + 1][next_ply];
                pv_length[ply] = pv_length[ply + 1];

                if (score >= beta) {
                    // Store TT entry
                    write_hash_entry(beta, depth, HASH_FLAG_BETA, best_move);

                    if (!is_capture) {
                        // Killer moves
                        killer_moves[1][ply] = killer_moves[0][ply];
                        killer_moves[0][ply] = move;
                        // Countermove heuristic
                        if (cm_piece)
                            countermove[cm_piece][cm_to] = move;
                        // v18: Continuation history update
                        if (cm_piece) {
                            int ch_bonus = depth * depth;
                            short *ch = &cont_hist[cm_piece][cm_to][get_move_piece(move)][get_move_target(move)];
                            int ch_val = (int)*ch + ch_bonus - (int)*ch * ch_bonus / 16384;
                            *ch = (short)(ch_val >  32767 ?  32767 : (ch_val < -32768 ? -32768 : ch_val));
                        }
                    } else {
                        // v18: Capture history update on cutoff
                        if (captured_piece_idx >= 0) {
                            int ch_bonus = depth * depth;
                            int *ch = &capture_history[get_move_piece(move)][get_move_target(move)][captured_piece_idx];
                            *ch += ch_bonus - *ch * ch_bonus / 16384;
                        }
                    }

                    return beta;
                }
            }
        }

        // History malus: penalize quiet moves that fail to improve alpha
        if (!is_capture && !is_promotion && score <= alpha) {
            int malus = depth * depth / 2;
            int *h = &history_moves[get_move_piece(move)][get_move_target(move)];
            *h -= malus + *h * malus / 16384;
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
    if (move_number < 10) moves_left = 25;
    else if (move_number < 30) moves_left = 20;
    else moves_left = 15;

    int base = my_time_ms / moves_left;
    base += (int)(my_inc_ms * 0.9);

    int max_time = my_time_ms / 3;
    int min_time = my_time_ms / 20;
    if (min_time > 500) min_time = 500;

    int budget = base;
    if (budget > max_time) budget = max_time;
    if (budget < min_time) budget = min_time;

    return budget;
}

// Save main-thread board state into master snapshot for worker threads
static void save_board_to_master(void) {
    memcpy(master_bitboards, bitboards, sizeof(bitboards));
    memcpy(master_occupancies, occupancies, sizeof(occupancies));
    master_side = side;
    master_enpassant = enpassant;
    master_castle = castle;
    master_hash_key = hash_key;
    memcpy(master_repetition_table, repetition_table, sizeof(repetition_table));
    master_repetition_index = repetition_index;
    master_ply = ply;
    memcpy(master_has_castled, has_castled, sizeof(has_castled));
    master_fullmove_number = fullmove_number;
    master_halfmove_clock = halfmove_clock;
}

// Copy master board state into the calling thread's TLS board state
static void copy_master_to_thread(void) {
    memcpy(bitboards, master_bitboards, sizeof(bitboards));
    memcpy(occupancies, master_occupancies, sizeof(occupancies));
    side = master_side;
    enpassant = master_enpassant;
    castle = master_castle;
    hash_key = master_hash_key;
    memcpy(repetition_table, master_repetition_table, sizeof(repetition_table));
    repetition_index = master_repetition_index;
    ply = master_ply;
    memcpy(has_castled, master_has_castled, sizeof(has_castled));
    fullmove_number = master_fullmove_number;
    halfmove_clock = master_halfmove_clock;
}

typedef struct {
    int thread_id;
    int max_depth;
} WorkerArgs;

static void* worker_thread(void* arg) {
    WorkerArgs* args = (WorkerArgs*)arg;

    // Initialize this thread's board state from master
    copy_master_to_thread();

    // Per-thread search state reset
    nodes = 0;
    prev_move_piece = 0;
    prev_move_to = 0;
    se_excluded_move = 0;
    memset(pv_table, 0, sizeof(pv_table));
    memset(pv_length, 0, sizeof(pv_length));

    int game_phase = get_game_phase();

    // Stagger starting depth by thread_id so threads explore different subtrees
    for (int current_depth = 1 + args->thread_id;
         current_depth <= args->max_depth && !stopped && !v14_stopped;
         current_depth++) {
        int search_depth = (game_phase < PHASE_THRESHOLD) ? current_depth + 1 : current_depth;
        negamax(-infinity, infinity, search_depth, 1);
    }

    return NULL;
}

// Search position: iterative deepening with aspiration windows
void search_position(int max_depth, int time_budget_ms)
{
    // Reset
    nodes = 0;
    v14_stopped = 0;
    stopped = 0;
    v14_search_start = get_time_ms();
    v14_time_budget_ms = time_budget_ms;

    memset(killer_moves, 0, sizeof(killer_moves));
    memset(history_moves, 0, sizeof(history_moves));
    memset(countermove, 0, sizeof(countermove));
    memset(capture_history, 0, sizeof(capture_history));
    memset(cont_hist, 0, sizeof(cont_hist));
    memset(pv_table, 0, sizeof(pv_table));
    memset(pv_length, 0, sizeof(pv_length));
    prev_move_piece = 0;
    prev_move_to = 0;
    se_excluded_move = 0;

    // Save board state for worker threads and spawn them
    pthread_t worker_threads[MAX_THREADS];
    WorkerArgs worker_args[MAX_THREADS];
    if (num_threads > 1) {
        save_board_to_master();
        for (int i = 1; i < num_threads; i++) {
            worker_args[i].thread_id = i;
            worker_args[i].max_depth = max_depth;
            pthread_create(&worker_threads[i], NULL, worker_thread, &worker_args[i]);
        }
    }

    int score = 0;
    int alpha = -infinity;
    int beta = infinity;
    int best_move_found = 0;  // Save best move across iterations

    // v16: score instability / easy move tracking
    int prev_best_move = 0;
    int move_stability = 0;
    int prev_score = 0;

    int game_phase = get_game_phase();

    // Minimum depth based on time budget
    int min_depth;
    if (time_budget_ms <= 0) min_depth = max_depth;
    else if (time_budget_ms < 2000) min_depth = 3;
    else if (time_budget_ms < 5000) min_depth = 4;
    else min_depth = 5;

    for (int current_depth = 1; current_depth <= max_depth; current_depth++) {
        // Time check: don't start new depth if 55%+ of budget used
        if (time_budget_ms > 0 && current_depth > min_depth) {
            long elapsed = get_time_ms() - v14_search_start;
            if (elapsed > (long)(time_budget_ms * 0.55))
                break;
        }

        if (v14_stopped) break;

        // Endgame extension: search 1 ply deeper when few pieces remain
        int search_depth = (game_phase < PHASE_THRESHOLD) ? current_depth + 1 : current_depth;

        // v16: Aspiration windows with gradual widening (50 -> 150 -> 450 -> full)
        if (current_depth <= 2) {
            alpha = -infinity;
            beta = infinity;
            score = negamax(alpha, beta, search_depth, 1);
        } else {
            int asp_delta = 50;
            alpha = score - asp_delta;
            beta = score + asp_delta;
            score = negamax(alpha, beta, search_depth, 1);

            // Widen window gradually on failure
            while (!v14_stopped && (score <= alpha || score >= beta)) {
                if (time_budget_ms > 0) {
                    long elapsed = get_time_ms() - v14_search_start;
                    if (elapsed > (long)(time_budget_ms * 0.7)) {
                        if (pv_length[0] > 0)
                            best_move_found = pv_table[0][0];
                        goto done;
                    }
                }
                if (score <= alpha) alpha = score - asp_delta;
                else               beta  = score + asp_delta;
                asp_delta *= 3;  // 50 -> 150 -> 450 -> full
                if (asp_delta >= 900) { alpha = -infinity; beta = infinity; }
                score = negamax(alpha, beta, search_depth, 1);
            }
        }

        if (v14_stopped) break;

        // This depth completed successfully — save the best move
        if (pv_length[0] > 0)
            best_move_found = pv_table[0][0];

        // v16: score instability / easy move detection
        {
            int score_swing = score - prev_score;
            if (score_swing < 0) score_swing = -score_swing;
            if (best_move_found == prev_best_move)
                move_stability++;
            else
                move_stability = 0;
            prev_best_move = best_move_found;
            prev_score = score;

            // Easy move: same best move for 3+ depths, small score swing, past 40% of budget
            if (current_depth > min_depth && time_budget_ms > 0
                && move_stability >= 3 && score_swing < 30) {
                long chk = get_time_ms() - v14_search_start;
                if (chk > (long)(time_budget_ms * 0.4)) break;
            }
        }

        // Print UCI info
        long elapsed = get_time_ms() - v14_search_start;
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
    // Stop and join worker threads
    if (num_threads > 1) {
        stopped = 1;  // ensure workers exit
        for (int i = 1; i < num_threads; i++)
            pthread_join(worker_threads[i], NULL);
    }

    // Print best move (use saved move, not pv_table which may be from incomplete depth)
    printf("bestmove ");
    if (best_move_found)
        print_move(best_move_found);
    else if (pv_length[0] > 0)
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
            // Hard safety: never use more than 40% of remaining clock minus overhead
            int hard = (int)(my_time * 0.4) - 1000;
            if (hard < time_budget_ms) hard = time_budget_ms;
            v14_hard_limit_ms = hard;
            search_depth = 30;
        } else if (wtime >= 0 || btime >= 0) {
            // Clock sent but our time is 0 (flagged / time scramble) — return a move fast
            time_budget_ms = 100;
            search_depth = 30;
        } else {
            // No time info at all — infinite search (e.g. "go infinite")
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
            break;  // EOF on stdin, exit

        // strip newline
        char *nl = strchr(input, '\n');
        if (nl) *nl = 0;

        if (input[0] == '\0')
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
            if (quit) break;
            continue;
        }

        if (strncmp(input, "quit", 4) == 0)
            break;

        if (strncmp(input, "perft", 5) == 0) {
            nodes = 0;
            int depth = atoi(input + 6);
            perft_test(depth);
            continue;
        }

        if (strncmp(input, "eval", 4) == 0) {
            printf("eval: %d\n", evaluate());
            fflush(stdout);
            continue;
        }

        if (strncmp(input, "stop", 4) == 0)
            continue;  // No-op when not searching

        if (strncmp(input, "setoption", 9) == 0) {
            if (strstr(input, "name Threads value")) {
                char *val = strstr(input, "value");
                if (val) {
                    int t = atoi(val + 6);
                    if (t >= 1 && t <= MAX_THREADS)
                        num_threads = t;
                }
            }
            continue;
        }

        if (strncmp(input, "uci", 3) == 0) {
            printf("id name v18\n");
            printf("id author tomberkley\n");
            printf("option name Threads type spin default 1 min 1 max %d\n", MAX_THREADS);
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

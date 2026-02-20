CC = gcc
CFLAGS = -O3 -Wall -Wno-unused-variable -Wno-unused-function
V14FLAGS = -O3 -march=native -fomit-frame-pointer -Wall -Wno-unused-variable -Wno-unused-function
LDFLAGS = -lm

all: v13_engine v14_engine v15_engine v16_engine v17_engine v18_engine

v13_engine: v13_engine.c
	$(CC) $(CFLAGS) -o v13_engine v13_engine.c $(LDFLAGS)

v14_engine: v14_engine.c
	$(CC) $(V14FLAGS) -o v14_engine v14_engine.c $(LDFLAGS)

v15_engine: v15_engine.c
	$(CC) $(V14FLAGS) -o v15_engine v15_engine.c $(LDFLAGS)

v16_engine: v16_engine.c
	$(CC) $(V14FLAGS) -o v16_engine v16_engine.c $(LDFLAGS)

v17_engine: v17_engine.c
	$(CC) $(V14FLAGS) -o v17_engine v17_engine.c $(LDFLAGS)

v18_engine: v18_engine.c
	$(CC) $(V14FLAGS) -o v18_engine v18_engine.c $(LDFLAGS)

clean:
	rm -f v13_engine v14_engine v15_engine v16_engine v17_engine v18_engine

.PHONY: all clean

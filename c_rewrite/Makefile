CC = gcc
CFLAGS = -O3 -Wall -Wno-unused-variable -Wno-unused-function
V14FLAGS = -O3 -march=native -fomit-frame-pointer -Wall -Wno-unused-variable -Wno-unused-function
LDFLAGS = -lm

all: v13_engine v14_engine v15_engine v16_engine v17_engine v18_engine v19_engine v20_engine v20_tuner v21_engine v22_engine v23_engine v24_engine

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
	$(CC) $(V14FLAGS) -pthread -o v18_engine v18_engine.c $(LDFLAGS)

v19_engine: v19_engine.c
	$(CC) $(V14FLAGS) -pthread -o v19_engine v19_engine.c $(LDFLAGS)

v20_engine: v20_engine.c
	$(CC) $(V14FLAGS) -pthread -o v20_engine v20_engine.c $(LDFLAGS)

v20_tuner: v20_engine.c
	$(CC) $(V14FLAGS) -DTUNER -o v20_tuner v20_engine.c -lm

v21_engine: v21_engine.c
	$(CC) $(V14FLAGS) -pthread -o v21_engine v21_engine.c $(LDFLAGS)

v22_engine: v22_engine.c
	$(CC) $(V14FLAGS) -pthread -o v22_engine v22_engine.c $(LDFLAGS)

v22_tuner: v22_engine.c
	$(CC) $(V14FLAGS) -DTUNER -o v22_tuner v22_engine.c -lm

v23_engine: v23_engine.c
	$(CC) $(V14FLAGS) -pthread -o v23_engine v23_engine.c $(LDFLAGS)

v23_tuner: v23_engine.c
	$(CC) $(V14FLAGS) -DTUNER -o v23_tuner v23_engine.c -lm

v24_engine: v24_engine.c
	$(CC) $(V14FLAGS) -pthread -o v24_engine v24_engine.c $(LDFLAGS)

v24_tuner: v24_engine.c
	$(CC) $(V14FLAGS) -DTUNER -o v24_tuner v24_engine.c -lm

clean:
	rm -f v13_engine v14_engine v15_engine v16_engine v17_engine v18_engine v19_engine v20_engine v20_tuner v21_engine v22_engine v22_tuner v23_engine v23_tuner v24_engine v24_tuner

.PHONY: all clean

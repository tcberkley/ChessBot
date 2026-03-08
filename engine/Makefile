CC = gcc
CFLAGS = -O3 -Wall -Wno-unused-variable -Wno-unused-function
V14FLAGS = -O3 -march=native -fomit-frame-pointer -Wall -Wno-unused-variable -Wno-unused-function
LDFLAGS = -lm

all: v1.0_engine v1.1_engine v1.2_engine v1.3_engine v1.4_engine v1.5_engine v1.6_engine v1.7_engine v1.7_tuner v1.8_engine v1.9_engine v1.10_engine v1.11_engine v2.0_engine v2.1_engine

v1.0_engine: v1.0_engine.c
	$(CC) $(CFLAGS) -o v1.0_engine v1.0_engine.c $(LDFLAGS)

v1.1_engine: v1.1_engine.c
	$(CC) $(V14FLAGS) -o v1.1_engine v1.1_engine.c $(LDFLAGS)

v1.2_engine: v1.2_engine.c
	$(CC) $(V14FLAGS) -o v1.2_engine v1.2_engine.c $(LDFLAGS)

v1.3_engine: v1.3_engine.c
	$(CC) $(V14FLAGS) -o v1.3_engine v1.3_engine.c $(LDFLAGS)

v1.4_engine: v1.4_engine.c
	$(CC) $(V14FLAGS) -o v1.4_engine v1.4_engine.c $(LDFLAGS)

v1.5_engine: v1.5_engine.c
	$(CC) $(V14FLAGS) -pthread -o v1.5_engine v1.5_engine.c $(LDFLAGS)

v1.6_engine: v1.6_engine.c
	$(CC) $(V14FLAGS) -pthread -o v1.6_engine v1.6_engine.c $(LDFLAGS)

v1.7_engine: v1.7_engine.c
	$(CC) $(V14FLAGS) -pthread -o v1.7_engine v1.7_engine.c $(LDFLAGS)

v1.7_tuner: v1.7_engine.c
	$(CC) $(V14FLAGS) -DTUNER -o v1.7_tuner v1.7_engine.c -lm

v1.8_engine: v1.8_engine.c
	$(CC) $(V14FLAGS) -pthread -o v1.8_engine v1.8_engine.c $(LDFLAGS)

v1.9_engine: v1.9_engine.c
	$(CC) $(V14FLAGS) -pthread -o v1.9_engine v1.9_engine.c $(LDFLAGS)

v1.9_tuner: v1.9_engine.c
	$(CC) $(V14FLAGS) -DTUNER -o v1.9_tuner v1.9_engine.c -lm

v1.10_engine: v1.10_engine.c
	$(CC) $(V14FLAGS) -pthread -o v1.10_engine v1.10_engine.c $(LDFLAGS)

v1.10_tuner: v1.10_engine.c
	$(CC) $(V14FLAGS) -DTUNER -o v1.10_tuner v1.10_engine.c -lm

v1.11_engine: v1.11_engine.c
	$(CC) $(V14FLAGS) -pthread -o v1.11_engine v1.11_engine.c $(LDFLAGS)

v1.11_tuner: v1.11_engine.c
	$(CC) $(V14FLAGS) -DTUNER -o v1.11_tuner v1.11_engine.c -lm

v2.0_engine: v2.0_engine.c fathom.c
	$(CC) $(V14FLAGS) -pthread -o v2.0_engine v2.0_engine.c fathom.c $(LDFLAGS)

v2.0_tuner: v2.0_engine.c fathom.c
	$(CC) $(V14FLAGS) -DTUNER -o v2.0_tuner v2.0_engine.c fathom.c -lm

v2.1_engine: v2.1_engine.c fathom.c
	$(CC) $(V14FLAGS) -pthread -o v2.1_engine v2.1_engine.c fathom.c $(LDFLAGS)

v2.1_tuner: v2.1_engine.c fathom.c
	$(CC) $(V14FLAGS) -DTUNER -o v2.1_tuner v2.1_engine.c fathom.c -lm

vTest_engine: vTest_engine.c fathom.c
	$(CC) $(V14FLAGS) -pthread -o vTest_engine vTest_engine.c fathom.c $(LDFLAGS)

vTest_tuner: vTest_engine.c
	$(CC) $(V14FLAGS) -DTUNER -o vTest_tuner vTest_engine.c -lm

clean:
	rm -f v1.0_engine v1.1_engine v1.2_engine v1.3_engine v1.4_engine v1.5_engine v1.6_engine v1.7_engine v1.7_tuner v1.8_engine v1.9_engine v1.9_tuner v1.10_engine v1.10_tuner v1.11_engine v1.11_tuner v2.0_engine v2.0_tuner v2.1_engine v2.1_tuner vTest_engine vTest_tuner

.PHONY: all clean

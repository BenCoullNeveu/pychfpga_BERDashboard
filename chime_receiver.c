/* 
 * chime_receiver.c - A simple UDP chime receiver
 * Sorts the arriving packets and writes to disk
 *  -- need to upgrade to use structs
 *  -- need to upgrade to read in configuration file for nchannels etc...
 * usage: chime_receiver <port>
 * started from http://www.cs.cmu.edu/afs/cs/academic/class/15213-f99/www/class26/udpserver.c
 */

#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <netdb.h>
#include <sys/types.h> 
#include <sys/socket.h>
#include <time.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <errno.h>
#include <signal.h>
#include "hdf5.h"
#include "hdf5_hl.h"

#define BUFSIZE 32767
#define nfreq 1024
#define ncorr 9*8/2


/*
 * error - wrapper for perror
 */
void error(char *msg) {
  perror(msg);
  exit(1);
}

void sig_handler(int sigNumber){
  if (sigNumber == SIGINT){
    printf("User interrupted, hopefully exiting nicely...\n");
    exit(0);
  }
}


int main(int argc, char **argv) {

//  int nfreq = 1024
//  ncorr = 8*(8+1)/2;
  int ntimes = 3600;
 
  typedef struct {
    int32_t real;  /* Real part */
    int32_t imag;  /* Imaginary part */
  } complex_t;

 typedef struct visibility
 {
  float   timestamp;
  int    antennaA;
  int    antennaB;
  int  corrNum;
  uint8_t rfi_flags[nfreq];
  uint8_t flags[nfreq];
  complex_t vis[nfreq];
 } visibility;

  visibility singleTime[ncorr];


  int sockfd; /* socket */
  int portno; /* port to listen on */
  int clientlen; /* byte size of client's address */
  struct sockaddr_in serveraddr; /* server's addr */
  struct sockaddr_in clientaddr; /* client addr */
  struct hostent *hostp; /* client host info */
  uint8_t buf[BUFSIZE]; /* message buf */
  char *hostaddrp; /* dotted decimal host addr string */
  int optval; /* flag value for setsockopt */
  int n; /* message byte size */
  char frame_id;  /* frame id*/
  char corr_number;
  char corr_frame_id_value;
  uint16_t mult_number;
  unsigned short stream_id;
  unsigned short word_length;
  unsigned int timestamp, lastTimestamp;
  int number_of_frames, nproducts;
  int freq_bin_product_number;
  int64_t productReal;
  int64_t productImag;
  int freq_channel;
  int freq_channel_offset;
  int i_index;
  int j_index;
  int linear_index;
  uint8_t flag;

  int64_t mask_34th_bit = 0x200000000; //0x0200000000
  int64_t to_int_mask = 0xFFFFFFFE00000000; //0xFFFFFFFE00000000;
  int decision;
  char fname[256];
  char outfname[256];
  float cstart_time;
  float system_frame_period = 2.56e-06;
  int file_write_loops;


  ///hdf5 stuff
  hsize_t dims = nfreq;  /* Change to use a complex struct instead */
  //hsize_t dims_flags = nfreq;

  hid_t          fid;        /* File identifier */
  hid_t          ptable;     /* Packet table identifier */
  //hid_t          ptable_flags;  /*  Packet table for flags */
  hid_t          my_dt;         /*  data type of row of data*/
  hid_t         dt_vis;   /* vis array data type */
  hid_t         dt_flags;   /* flags array data type */
  hid_t         dt_rfi_flags;  /* number of samples in integration flagged as rfi */

  herr_t         err;        /* Function return status */
  hsize_t        count;      /* Number of records in the table */
  hid_t         complex_dt;  /* define complex data type  */

  int            x;          /* Loop variable */
  int stop = 0;
  int nappends = 0;



  ////int64_t singleTime[ncorr][2*nfreq];
  ////uint8_t flags[ncorr][nfreq];
  int32_t first;
  clock_t tic;
  clock_t toc;
  clock_t total;
  FILE *fp;
  /* 
   * check and use command line arguments 
   */
  if (argc != 5) {
    fprintf(stderr, "usage: %s <net/disk> <port/filename> <outfile> <float cstart_time>\n", argv[0]);
    exit(1);
  }

  if (strcmp(argv[1], "net") == 0){
      portno = atoi(argv[2]);
      decision = 1;
      file_write_loops = 3000;


    /* 
     * socket: create the parent socket 
     */
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0) 
      error("ERROR opening socket");

    /* setsockopt: Handy debugging trick that lets 
     * us rerun the server immediately after we kill it; 
     * otherwise we have to wait about 20 secs. 
     * Eliminates "ERROR on binding: Address already in use" error. 
     */
    optval = 1;
    setsockopt(sockfd, SOL_SOCKET, SO_REUSEADDR, 
  	     (const void *)&optval , sizeof(int));
    

    /*
     * build the server's Internet address
     */
    memset((char *) &serveraddr, 0, sizeof(serveraddr));
    serveraddr.sin_family = AF_INET;
    serveraddr.sin_addr.s_addr = htonl(INADDR_ANY);
    serveraddr.sin_port = htons((unsigned short)portno);

    /* 
     * bind: associate the parent socket with a port 
     */
    if (bind(sockfd, (struct sockaddr *) &serveraddr, 
  	   sizeof(serveraddr)) < 0) 
      error("ERROR on binding");

    /* 
     * main loop: wait for a datagram, sort and write to disk
     */
    clientlen = sizeof(clientaddr);
    //printf("buffer size %d\n", BUFSIZE);

  }
  else if (strcmp(argv[1], "disk") == 0){
    strcpy(fname, argv[2]);

    fp=fopen( fname, "rb");
    if (fp == NULL){
      error("Error opening the file...\n");
    }
    decision = 2;
    file_write_loops = 1;
  }



  cstart_time = atof(argv[4]);

  //Initialize HDF5 file and datatypes





  complex_dt = H5Tcreate( H5T_COMPOUND, sizeof(complex_t));
  err = H5Tinsert(complex_dt, "real", HOFFSET(complex_t, real), H5T_NATIVE_INT);
  err = H5Tinsert(complex_dt, "imag", HOFFSET(complex_t, imag), H5T_NATIVE_INT);

  //hid_t H5Tarray_create( hid_t base_typ_id, unsigned rank, const hsize_t dims[/*rank*/], )
  dt_vis = H5Tarray_create2( complex_dt, 1,  &dims );
  dt_flags = H5Tarray_create2( H5T_NATIVE_UCHAR, 1, &dims );
  dt_rfi_flags = H5Tarray_create2( H5T_NATIVE_UCHAR, 1, &dims );

  my_dt = H5Tcreate(H5T_COMPOUND, sizeof(visibility));

  err = H5Tinsert(my_dt, "timestamp", HOFFSET(visibility, timestamp), H5T_NATIVE_FLOAT);
  err = H5Tinsert(my_dt, "antennaA", HOFFSET(visibility, antennaA), H5T_NATIVE_INT);
  err = H5Tinsert(my_dt, "antennaB", HOFFSET(visibility, antennaB), H5T_NATIVE_INT);
  err = H5Tinsert(my_dt, "CorrNumber", HOFFSET(visibility, corrNum), H5T_NATIVE_INT);
  err = H5Tinsert(my_dt, "RFI_count", HOFFSET(visibility, rfi_flags), dt_flags);
  err = H5Tinsert(my_dt, "Flags", HOFFSET(visibility, flags), dt_flags);
  err = H5Tinsert(my_dt, "visibilities", HOFFSET(visibility, vis), dt_vis);
  

  //ptable_flags = H5PTcreate_fl(fid, "Data_flags", dt_flags, (hsize_t)1, -1);

  /* Start Parsing correlator data */

  corr_frame_id_value = (char) 0xF0;



  for (int loop_number = 0; loop_number < file_write_loops; ++loop_number)
  {

  //strcpy(outfname, argv[3]);
  sprintf(outfname, "%s.%04d", argv[3], loop_number);
  fid=H5Fcreate(outfname,H5F_ACC_TRUNC,H5P_DEFAULT,H5P_DEFAULT);
  //hid_t H5PTcreate_fl( hid_t loc_id, const char * dset_name, hid_t dtype_id, hsize_t chunk_size, int compression )
  ptable = H5PTcreate_fl(fid, "Correlator_Data", my_dt, (hsize_t)1, -1);
  lastTimestamp = 0;
  first = 1;

  // FILE *fp;
  // fp=fopen("test.bin", "wb");
  number_of_frames = 0;
  tic = clock();
  x=0;
  
  while (x < 3600) {

    signal(SIGINT, sig_handler);
    /*
     * recvfrom: receive a UDP datagram or read from file
     */
    memset(buf, 0, BUFSIZE);
    if (decision == 1){
          n = recvfrom(sockfd, buf, BUFSIZE, 0,
           (struct sockaddr *) &clientaddr, &clientlen);
          if (n < 0)
            error("ERROR in recvfrom");
          //printf("number of bytes received: %d\n", n);
    }
    else if (decision == 2){
      if (feof(fp)){
        printf("End of file reached before expected to... got %d times\n", x);
        exit(0);
      }
      n = fread(buf, sizeof(uint8_t), 6459, fp);
      if (n < 0)
        error("ERROR in file read...");
        //printf("number of bytes received: %d\n", n);
      if (feof(fp)){
        timestamp = 1;
        buf[0] = corr_frame_id_value;
        //printf("%d, %d, %x\n", x, number_of_frames, buf[0]);
      }
    }

    frame_id = buf[0] & 0xF0;
    if ( frame_id == corr_frame_id_value ) { /*  Got a correlator frame*/
      //printf("got a frame\n");
      /* unpack the header*/
      corr_number = buf[0] & 0x0F;
      mult_number = (uint16_t) (((uint16_t)buf[1]<<8) | (buf[2]));
      stream_id = (uint16_t) (((uint16_t)buf[3]<<8) | (buf[4]));
      word_length = (uint16_t) (((uint16_t)buf[5]<<8) | (buf[6]));
      timestamp = (uint32_t) (((uint32_t)buf[7]<<24) | ((uint32_t)buf[8]<<16) | ((uint32_t)buf[9]<<8) | buf[10]);
      if (first == 1){
        lastTimestamp = timestamp;
        first = 0;
      }
      if (lastTimestamp != timestamp){  /* Write to disk if got a new timestamp and initialize array to max value. First timestamp most likely not full.*/
        for (int i = 0; i < ncorr; ++i)
        {
          err = H5PTappend(ptable, (hsize_t)1, &(singleTime[i]) );
        }
        //err = H5PTappend(ptable_flags, (hsize_t)1, &(flags));
        //printf("wrote frame to disk...\n");
        lastTimestamp = timestamp;
        //toc = clock();
        //printf("number of frames gotten:%d\n", number_of_frames);
        // printf(". ");
        // fflush(stdout);
        if( number_of_frames < 72)
          printf("got only %d out of 72 frames ###############################################################\n", number_of_frames);
        //printf("time to unscramble frames: %f seconds\n", (double)(toc-tic)/CLOCKS_PER_SEC);
        //tic = clock();
        number_of_frames = 0;
        x += 1;
        memset(singleTime, 0, sizeof(visibility));
      //   for (int i = 0; i < ncorr; ++i)
      //   {
      //     for (int j = 0; j < nfreq; ++j)
      //     {
      //       singleTime[i].visReal[j]= (int64_t) -2147483648;
      //       singleTime[i].visImag[j]= (int64_t) -2147483648;
      //       //singleTimeImag[i][j]=0;
      //     }
      //   }
      }


      /* Unscramble incoming data. and put in singleTime array. */
      nproducts = (n-11)/13;
      //printf("Nproducs is %d\n", nproducts);
      for (int i = 0; i < nproducts; ++i)
      {
        productReal =  ((((int64_t)buf[11+i*13+1] << 40) | ((uint64_t)buf[11+i*13+2] << 32) | ((uint64_t)buf[11+i*13+3] << 24) | ((uint64_t)buf[11+i*13+4] << 16) | ((uint64_t)buf[11+i*13+5] << 8) | ((uint64_t)buf[11+i*13+6])));
        // if(buf[11+i*13+1] == (int8_t) 0x00){
        //     printf("Got some zeros...\n");  /* Looks like are all zeros */
        // }
        productImag = ((((int64_t)buf[11+i*13+7] << 40) | ((uint64_t)buf[11+i*13+8] << 32) | ((uint64_t)buf[11+i*13+9] << 24) | ((uint64_t)buf[11+i*13+10] << 16) | ((uint64_t)buf[11+i*13+11] << 8) | ((uint64_t)buf[11+i*13+12])));
        if( (productReal & mask_34th_bit) != (int64_t) 0 ) {
          //printf("%#llX\n", productReal);
          productReal = productReal | (int64_t) to_int_mask;
          //printf("%#llX\n", productReal);
          //printf("%x %x\n", buf[11+i*13+1], buf[11+i*13+2]);
          //printf("Masking, not sure how i got here\n");
        }
        if( (productImag & mask_34th_bit) != (int64_t) 0 ) {
          productImag = productImag | to_int_mask;
          //printf("%x %x\n", buf[11+i*13+7], buf[11+i*13+8]);
        }
        flag = buf[i*13];
        //productReal = productReal >> 16;
        //productImag = productImag >> 16;
        freq_bin_product_number = i % 8;
        freq_channel = (i/8)*16 + (int)corr_number*2;
        //printf("freq_bin_prod_number %d, freq_channel %d", freq_bin_product_number, freq_channel);
        if (mult_number == (uint16_t) 0){
          i_index = 7 - freq_bin_product_number;
          j_index = 7 - freq_bin_product_number;
          freq_channel_offset = 1;
          //printf("Got in 0\n");
        }
        else if ( mult_number == (uint16_t) 8 ){
          i_index = freq_bin_product_number;
          j_index = freq_bin_product_number;
          freq_channel_offset = 0;
          //printf("Got in 1\n");
        }
        else if (freq_bin_product_number < (int) mult_number){
          i_index = 7 - (int) mult_number;
          j_index = 8 - (int) mult_number + freq_bin_product_number;
          freq_channel_offset = 0;
          //printf("Got in 2\n");
        }
        else {
          i_index = (int) mult_number - 1;
          j_index = mult_number + 7 - freq_bin_product_number;
          freq_channel_offset = 1;
          //printf("Got in 3\n");
        }
        linear_index = i_index*8 - i_index*(i_index+1)/2 + j_index;
        //printf("%ld +i%ld\n", productReal, productImag);
        //printf("linear_index: %d, freq_channel: %d, freq_channel_offset %d, data: %d +i%d\n", linear_index, freq_channel, freq_channel_offset, (int) productReal, (int)productImag);
        //printf("linear_index: %d, freq_channel: %d, freq_channel_offset %d, data: %ld +i%ld\n", linear_index, freq_channel, freq_channel_offset, productReal, productImag);
        //################## populate struct, could be much more efficient, overpopulating most.   
        singleTime[linear_index].vis[(freq_channel+freq_channel_offset)].real = (int32_t) productReal;
        singleTime[linear_index].vis[(freq_channel+freq_channel_offset)].imag = (int32_t) productImag;
        singleTime[linear_index].flags[freq_channel+freq_channel_offset] = flag;
        singleTime[linear_index].antennaA = i_index;
        singleTime[linear_index].antennaB = j_index;
        singleTime[linear_index].corrNum = linear_index;
        singleTime[linear_index].timestamp = cstart_time + timestamp*system_frame_period;
      }
      number_of_frames=number_of_frames+1;
    }
    //printf("%hhX, %hhX, %hhX, %hX, %hX, %X \n", frame_id, corr_number, mult_number, stream_id, word_length, timestamp);
    // printf("%x\n", frame_id);
    // //printf("%hhd ", buf[i]);
    // for (int i = 0; i < n; ++i)
    //  {
    //    printf("%x ", buf[i]);
    //  }
    //  printf("\n");

  }
    err = H5PTclose(ptable);
    H5Fclose(fid);
  } 

}

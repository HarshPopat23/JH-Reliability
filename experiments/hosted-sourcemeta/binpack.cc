#include <sourcemeta/jsonbinpack/compiler.h>
#include <sourcemeta/jsonbinpack/runtime.h>
#include <sourcemeta/core/json.h>
#include <sourcemeta/core/jsonschema.h>
#include <chrono>
#include <iostream>
#include <sstream>
using Clock=std::chrono::steady_clock;
auto ns(Clock::time_point t){return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-t).count();}
int main(int argc,char**argv){try{
 auto schema=sourcemeta::core::read_json(argv[1]); auto instance=sourcemeta::core::read_json(argv[2]);
 auto start=Clock::now();
 sourcemeta::jsonbinpack::compile(schema,sourcemeta::core::schema_walker,sourcemeta::core::schema_resolver,"https://json-schema.org/draft/2020-12/schema");
 auto encoding=sourcemeta::jsonbinpack::load(schema); auto compile_ns=ns(start);
 std::uint64_t encode_ns=0,decode_ns=0,bytes=0,correct=0; const int rounds=1000;
 for(int i=0;i<rounds;i++){
  std::stringstream stream(std::ios::in|std::ios::out|std::ios::binary);
  start=Clock::now(); sourcemeta::jsonbinpack::Encoder encoder{stream}; encoder.write(instance,encoding); encode_ns+=ns(start);
  bytes=stream.str().size(); stream.seekg(0);
  start=Clock::now(); sourcemeta::jsonbinpack::Decoder decoder{stream}; auto decoded=decoder.read(encoding); decode_ns+=ns(start);
  if(decoded==instance) correct++; else return 3;
 }
 std::cout<<"{\"compile_ns\":"<<compile_ns<<",\"rounds\":"<<rounds<<",\"bytes\":"<<bytes<<",\"encode_ns_total\":"<<encode_ns<<",\"decode_ns_total\":"<<decode_ns<<",\"correct\":"<<correct<<"}"<<std::endl;
}catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 2;}}

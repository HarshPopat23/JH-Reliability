#include <sourcemeta/blaze/compiler.h>
#include <sourcemeta/blaze/evaluator.h>
#include <sourcemeta/blaze/alterschema.h>
#include <sourcemeta/core/json.h>
#include <sourcemeta/core/jsonschema.h>
#include <chrono>
#include <filesystem>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
using Clock = std::chrono::steady_clock;
auto ns(Clock::time_point t) { return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-t).count(); }
int main(int argc, char **argv) {
 try {
  if(argc==3 && std::string(argv[1])=="transform") {
   auto schema=sourcemeta::core::read_json(argv[2]);
   sourcemeta::blaze::SchemaTransformer transformer;
   sourcemeta::blaze::add(transformer,sourcemeta::blaze::AlterSchemaMode::Linter);
   transformer.apply(schema,sourcemeta::core::schema_walker,sourcemeta::core::schema_resolver,
    [](const auto&,const auto&,const auto&,const auto&,const auto){});
   sourcemeta::core::prettify(schema,std::cout); std::cout << std::endl; return 0;
  }
  std::map<std::string,sourcemeta::blaze::Template> compiled;
  auto start=Clock::now();
  for(const auto &entry:std::filesystem::directory_iterator(argv[1])) {
   if(entry.path().extension()!=".json") continue;
   auto schema=sourcemeta::core::read_json(entry.path());
   compiled.emplace(entry.path().stem().string(),sourcemeta::blaze::compile(schema,sourcemeta::core::schema_walker,sourcemeta::core::schema_resolver,sourcemeta::blaze::default_schema_compiler));
  }
  std::cout << "{\"ready\":true,\"schemas\":" << compiled.size() << ",\"compile_ns\":" << ns(start) << "}" << std::endl;
  sourcemeta::blaze::Evaluator evaluator;
  std::string line;
  while(std::getline(std::cin,line)) {
   std::istringstream stream(line); std::string key,count,payload;
   std::getline(stream,key,'\t'); std::getline(stream,count,'\t'); std::getline(stream,payload);
   auto parse_start=Clock::now(); auto instance=sourcemeta::core::parse_json(payload); auto parse_ns=ns(parse_start);
   const auto &program=compiled.at(key); const auto iterations=std::stoull(count);
   if(iterations<1 || iterations>1000000) return 3;
   std::uint64_t checksum=0; auto engine_start=Clock::now();
   for(std::uint64_t i=0;i<iterations;i++) checksum+=evaluator.validate(program,instance)?1:0;
   auto elapsed=ns(engine_start);
   std::cout << "{\"valid\":" << (checksum==iterations?"true":"false") << ",\"checksum\":" << checksum << ",\"iterations\":" << iterations << ",\"engine_ns\":" << elapsed << ",\"parse_ns\":" << parse_ns << "}" << std::endl;
  }
 } catch(const std::exception &e) { std::cerr << e.what() << std::endl; return 2; }
}

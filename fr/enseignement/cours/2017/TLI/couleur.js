var id = document.getElementById("imageData");
var context = id.getContext("2d");
var img = new Image();
img.src = "800px-Detailaufnahme_Weihnachtsstern_-_groß.bmp";
context.drawImage(img, 200, 0, 400, 600);

function imageData(r, g, b) {
  context.clearRect(0, 0, 400, 600)
  context.drawImage(img, 200, 0, 400, 600);
  var data = context.getImageData(200, 0, 400, 600);
  for(i=0; i< data.data.length; i+=3)
    if(data.data[i] > r - 20  && data.data[i] < r + 20 &&
       data.data[i+1] > g - 20 && data.data[i + 1] < g + 20 &&
       data.data[i+2] > b - 20 && data.data[i + 1] < b + 20) {
      data.data[i]=205;
      data.data[i+1]=205;
      data.data[i+2]=205;
    }
  context.putImageData(data, 200, 0);
}


function imageCouleur() {
  var input = document.getElementById("couleur");
  var r = parseInt(input.value.substr(1,2), 16);
  var g = parseInt(input.value.substr(3,2), 16);
  var b = parseInt(input.value.substr(5,2), 16);
  imageData(r, g, b);
}
